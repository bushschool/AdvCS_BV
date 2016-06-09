import numpy as np
import numpy.linalg as linalg
from primesense import openni2
from matplotlib import pyplot as plt
import sys

"""
Averages n depth frames, returns world coodinates of 2d depth pixel coordinates given in pts array
Also takes depth stream (ds) instance for reference
"""
def fetchDepthFrames(ds, n):
    #fetch n sequential frames
    frames = [None] * n
    for i in range(n):
        f = ds.read_frame().get_buffer_as_uint16()
        frames[i] = np.ndarray((480,640),dtype=np.uint16,buffer=f)
        plt.pause(1.0/30) #assume 30 fps
    return frames

def processDepthFrames(ds, frames, pts):
    #get a median non-0 depth value
    ipts = [None] * len(pts)
    i = 0
    for x,y in pts:
        ipts[i] = (x, y, np.median([f[y][x] for f in frames if f[y][x] != 0])) #ignore 0 values (out of measuring range)
        i += 1

    fpts = [None] * len(pts)
    for i in range(len(ipts)):
        fpts[i] = openni2.convert_depth_to_world(ds, ipts[i][0], ipts[i][1], ipts[i][2])
    return fpts

"""
dumb inefficient but necessary method to get depth point from color
ds - depth stream
cs - color stream
dframe - depth frame (as np array)
pt - color point to convert
"""
def colorToDepth(ds, cs, dframe, pt):
    guess = pt #guess for which depth point it is, start by assuming they're same point
    bestErr = sys.maxint
    bestGuess = None
    while True:
        cpt = openni2.convert_depth_to_color(ds, cs, guess[0], guess[1], dframe[guess[0]][guess[1]])

         #check if its right or hit local minimum (then just give up and give best one)
        if cpt == pt or ((cpt[0] - pt[0])**2 + (cpt[1] - pt[1])**2) > bestErr:
            return bestGuess
        bestErr = (cpt[0] - pt[0])**2 + (cpt[1] - pt[1])**2
        bestGuess = guess

        if cpt[0] < pt[0]:
            guess[0] += 1
        elif cpt[0] > pt[0]:
            guess[0] -= 1
        if cpt[1] < pt[1]:
            guess[1] += 1
        elif cpt[1] > pt[1]:
            guess[1] -= 1

"""
Get the equation of a plane given a 3x3 matrix of Euclidean 3D coords that it passes through
"""
def planeFromPts(pts):
    n = np.cross(np.squeeze(np.asarray(pts[:,2]))-np.squeeze(np.asarray(pts[:,0])),\
                 np.squeeze(np.asarray(pts[:,2]))-np.squeeze(np.asarray(pts[:,1])))
    return (n[0], n[1], n[2], -np.dot(n, np.asarray(pts[:,2]))[0])

"""
Fit a plane to the given list of points
"""
def fitPlane(pts):
    xs = np.array([pt[0] for pt in pts])
    ys = np.array([pt[1] for pt in pts])
    zs = np.array([pt[2] for pt in pts])
    sxx = sum(xs**2)
    sxy = sum(xs*ys)
    syy = sum(ys**2)
    sx = sum(xs)
    sy = sum(ys)
    a = np.matrix([[sxx, sxy, sx],\
                   [sxy, syy, sy],\
                   [sx,  sy,  len(pts)]])
    b = np.matrix([[sum(xs*zs)], [sum(ys*zs)], [sum(zs)]])
    x = np.asarray(a.I * b).flatten()
    return (x[0], x[1], x[2], np.mean([-np.dot(pt, x) for pt in pts]))

"""
~done but not tested~
Given pixel/distance coords from Kinect, figure out real world [x,y,z] coords
pts is a numpy matrix of [x,y,z] col vectors for kinect x/y pixels and z distance
"""
def rwCoordsFromKinect(pts):
    #constants in the equation
    kx = (640/2) / np.tan(np.radians(57.0/2))
    ky = (480/2) / np.tan(np.radians(43.0/2))

    newx = [0] * pts.shape[1]
    newy = [0] * pts.shape[1]
    newz = [0] * pts.shape[1]

    for i in range(pts.shape[1]): #for each column vector
        newx[i] = pts[2,i] / np.sqrt((kx/pts[0,i])**2 + 1)
        newy[i] = pts[2,i] / np.sqrt((ky/pts[1,i])**2 + 1)
        newz[i] = np.sqrt(pts[2,i]**2 - newx[i]**2)

    return [(newx[i], newy[i], newz[i]) for i in range(len(newx))]

"""
Magnitude of a numpy array
"""
def mag(array):
    return np.sqrt(sum([el**2 for el in array]))

"""
Square magnitude of a numpy array
"""
def sqmag(array):
    return sum([el**2 for el in array])

"""
Return the unit vector version of this array
"""
def normalized(array):
    return array / mag(array)

"""
Get 3x3 2D homogenous perspective transform matrix given source and destination points
"""
def getPTMat(src, dst):
    a = getHGFromPts(src)
    b = getHGFromPts(dst)
    return b * a.I

"""
Part of getPTMat technique - scales homogenous coords to prepare creation of transform matrix
"""
def getHGFromPts(pts): #take 3x4 homogenous matrix of column points, return 3x3
    m1 = pts[:,:-1]
    m2 = pts[:,-1]
    coeffs = m1.I * m2
    return np.multiply(np.matrix([coeffs.A1.tolist()] * 3), m1)

"""
Convert a matrix of homogenous coords to list of tuple Euclidean coords
"""
def hgToEuc(m):
    return [(m[0,i]/m[2,i], m[1,i]/m[2,i]) for i in range(m.shape[1])]

def hgToEuc3D(m):
    return [(m[0,i]/m[3,i], m[1,i]/m[3,i], m[2,i]/m[3,i]) for i in range(m.shape[1])]

def hgToEuc3DArray(m):
    return [(el[0]/el[3], el[1]/el[3], el[2]/el[3]) for el in m]

"""
Skew-symmetric cross product
"""
def sscp(v):
    return np.matrix([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])

"""
Gets angle between vectors
"""
def angBtwn(v1, v2):
    return np.arccos(np.dot(v1, v2)/(mag(v1)*mag(v2)))

"""
Gives the transform between A and B, two Nx3 matrices of column vectors.
Transform represented as p' = Rp + t
Returns R,t
Uses nasty linear algebra stuff, so approach is HEAVILY based on: http://nghiaho.com/uploads/code/rigid_transform_3D.py_
"""
def rigid_transform(A, B):
    if len(A) != len(B):
        print "Matrix dimension mismatch in rigid transform"
        return None
    n = A.shape[0]

    #get centroids
    ctrA = np.mean(A, axis=0)
    ctrB = np.mean(B, axis=0)

    #adjust shapes to have same center
    AA = A - np.tile(ctrA, (n, 1))
    BB = B - np.tile(ctrB, (n, 1))

    #gross...
    H = AA.T * BB
    U, S, Vt = linalg.svd(H)
    R = Vt.T * U.T
    if linalg.det(R) < 0:
        Vt[2,:] *= -1
        R = Vt.T * U.T
    t = -R*ctrA.T + ctrB.T

    return R, t