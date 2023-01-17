import configparser
import csv
import fnmatch
import math
import operator
import os.path
import random
import shutil
import time
import time as t
import xml.etree.ElementTree
from xml.etree.ElementTree import tostring

import SimpleITK as sitk
import ctk
import numpy as np
import sitkUtils
import slicer
import vtk
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

import Resources.utils as u
from Resources.constants.matArcLen_mm import matArcLen_mm
from Resources.constants.matEndSegAngles_rad import matEndSegAngles_rad
from Resources.constants.matFs_mN import matFs_mN
from Resources.constants.matYDefl_mm import matYDefl_mm


def factorial(n):
    """
    factorial(n): return the factorial of the integer n.
    factorial(0) = 1
    factorial(n) with n<0 is -factorial(abs(n))
    """
    result = 1
    for i in range(1, abs(n) + 1):
        result *= i
    if n >= 0:
        return result
    else:
        return -result


def binomial(n, k):
    """
    binomial coefficient
    """
    if not 0 <= k <= n:
        return 0
    if k == 0 or k == n:
        return 1
    # calculate n!/k! as one product, avoiding factors that
    # just get canceled
    P = k + 1
    for i in range(k + 2, n + 1):
        P *= i
    # if you are paranoid:
    # C, rem = divmod(P, factorial(n-k))
    # assert rem == 0
    # return C
    return P // factorial(n - k)


def fibonacci(n):
    """
    Fibonacci
    """
    F = [0, 1]
    for i in range(1, n + 1):
        F.append(F[i - 1] + F[i])
    return F


def stepSize(k, l):
    """
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle
    """
    # productive
    F = fibonacci(l)
    s = F[k + 1] / float(sum(fibonacci(l)))
    return s


def stepSizeAndre(k, l):
    """
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle
    """
    # productive
    F = fibonacci(l)
    s = F[k + 1] / float(sum(fibonacci(l)) - 1)
    return s


def stepSize13(k, l):
    """MICCAI13 version
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle
    """
    F = fibonacci(l + 1)
    s = (sum(fibonacci(k + 1), -1) + F[k + 1]) / float(
        sum(fibonacci(l + 1), -1)
    )
    return s


def sortTable(table, cols):
    """
    sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    # productive
    u.profprint()
    for col in reversed(cols):
        table = sorted(table, key=operator.itemgetter(col))
    return table


def sortTableReverse(table, cols):
    """
    sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    # productive
    u.profprint()
    for col in reversed(cols):
        table = sorted(table, key=operator.itemgetter(col), reverse=True)
    return table


def ijk2ras(A, volumeNode=None):
    """
    Convert IJK coordinates to RAS coordinates. The transformation matrix is the one
    of the active volume on the red slice
    """
    m = vtk.vtkMatrix4x4()
    if volumeNode is None:
        volumeNode = (
            slicer.app.layoutManager()
            .sliceWidget("Red")
            .sliceLogic()
            .GetBackgroundLayer()
            .GetVolumeNode()
        )
    volumeNode.GetIJKToRASMatrix(m)
    ras = [0, 0, 0]
    k = vtk.vtkMatrix4x4()
    o = vtk.vtkMatrix4x4()
    k.SetElement(0, 3, A[0])
    k.SetElement(1, 3, A[1])
    k.SetElement(2, 3, A[2])
    k.Multiply4x4(m, k, o)
    ras[0] = o.GetElement(0, 3)
    ras[1] = o.GetElement(1, 3)
    ras[2] = o.GetElement(2, 3)
    return ras


def ras2ijk(A, volumeNode=None):
    """
    Convert RAS coordinates to IJK coordinates. The transformation matrix is the one
    of the active volume on the red slice
    """
    m = vtk.vtkMatrix4x4()
    if volumeNode is None:
        volumeNode = (
            slicer.app.layoutManager()
            .sliceWidget("Red")
            .sliceLogic()
            .GetBackgroundLayer()
            .GetVolumeNode()
        )
    volumeNode.GetIJKToRASMatrix(m)
    m.Invert()
    ijk = [0, 0, 0]
    k = vtk.vtkMatrix4x4()
    o = vtk.vtkMatrix4x4()
    k.SetElement(0, 3, A[0])
    k.SetElement(1, 3, A[1])
    k.SetElement(2, 3, A[2])
    k.Multiply4x4(m, k, o)
    ijk[0] = o.GetElement(0, 3)
    ijk[1] = o.GetElement(1, 3)
    ijk[2] = o.GetElement(2, 3)
    return ijk


def displayBentNeedle(i):
    """
    not actively used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    """
    u.profbox()
    # obsolete
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        if (
                modelNode.GetAttribute("nth") == str(i)
                and modelNode.GetAttribute("optimized") == "1"
        ):
            displayNode = modelNode.GetModelDisplayNode()
            nVisibility = displayNode.GetVisibility()
            # print nVisibility
            if nVisibility:
                displayNode.SliceIntersectionVisibilityOff()
                displayNode.SetVisibility(0)
            else:
                displayNode.SliceIntersectionVisibilityOn()
                displayNode.SetVisibility(1)


def displayNeedle(i):
    """
    ??? not used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    """
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        if (
                modelNode.GetAttribute("nth") == str(i)
                and modelNode.GetAttribute("segmented") == "1"
        ):
            displayNode = modelNode.GetModelDisplayNode()
            nVisibility = displayNode.GetVisibility()

            if nVisibility:
                displayNode.SliceIntersectionVisibilityOff()
                displayNode.SetVisibility(0)
            else:
                displayNode.SliceIntersectionVisibilityOn()
                displayNode.SetVisibility(1)


def displayRadPlanned():
    """
    Display 'radiation' of planned needle -> cf iGyne / not used anymore
    """
    # obsolete?
    u.profbox()
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        displayNode = modelNode.GetDisplayNode()
        if modelNode.GetAttribute("radiation") == "planned":
            needleNode = slicer.mrmlScene.GetNodeByID(
                modelNode.GetAttribute("needleID")
            )
            if needleNode.GetDisplayVisibility() == 1:
                modelNode.SetDisplayVisibility(
                    abs(
                        int(
                            slicer.modules.NeedleFinderWidget.displayRadPlannedButton.checked
                        )
                        - 1
                    )
                )


def displayRadSegmented():
    """
    Display 'radiation' of segmented needles
    ??? used?
    """
    # obsolete?
    u.profbox()
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        if modelNode.GetAttribute("radiation") == "segmented":
            needleNode = slicer.mrmlScene.GetNodeByID(
                modelNode.GetAttribute("needleID")
            )
            if needleNode != None:
                if needleNode.GetDisplayVisibility() == 1:
                    modelNode.SetDisplayVisibility(
                        abs(
                            int(
                                slicer.modules.NeedleFinderWidget.displayRadSegmentedButton.checked
                            )
                            - 1
                        )
                    )
                    d = modelNode.GetDisplayNode()
                    d.SetSliceIntersectionVisibility(
                        abs(
                            int(
                                slicer.modules.NeedleFinderWidget.displayRadSegmentedButton.checked
                            )
                            - 1
                        )
                    )


def displayContour(i, visibility):
    """
    Display the iso-contour of needle i

    :param i: nth value of needle
    :param visibility: boolean to set the visibility state of the needle
    ??? used?
    """
    # obsolete?
    u.profbox()
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        if modelNode.GetAttribute("contour") == "1" and modelNode.GetAttribute(
                "nth"
        ) == str(i):
            needleNode = slicer.mrmlScene.GetNodeByID(
                modelNode.GetAttribute("needleID")
            )
            if needleNode != None:
                if needleNode.GetDisplayVisibility() == 1:
                    modelNode.SetDisplayVisibility(visibility)
                    d = modelNode.GetDisplayNode()
                    d.SetSliceIntersectionVisibility(visibility)


def displayContours():
    """
    Display or hide the iso-contours of every needles
    ??? used?
    """
    # obsolete?
    u.profbox()
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    for modelNode in list(modelNodes.values()):
        if modelNode.GetAttribute("contour") == "1":
            needleNode = slicer.mrmlScene.GetNodeByID(
                modelNode.GetAttribute("needleID")
            )
            if needleNode != None:
                if needleNode.GetDisplayVisibility() == 1:
                    modelNode.SetDisplayVisibility(
                        abs(
                            int(
                                slicer.modules.NeedleFinderWidget.displayContourButton.checked
                            )
                            - 1
                        )
                    )
                    d = modelNode.GetDisplayNode()
                    d.SetSliceIntersectionVisibility(
                        abs(
                            int(
                                slicer.modules.NeedleFinderWidget.displayContourButton.checked
                            )
                            - 1
                        )
                    )


def resetCoronalSegment():
    """
    Reset coronal segment orientation.
    """
    # research
    u.profprint()
    sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
    if sGreen is None:
        sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode3")
    reformatLogic = slicer.vtkSlicerReformatLogic()
    sGreen.SetOrientationToCoronal()
    sGreen.Modified()


def resetSagittalSegment():
    """
    Reset sagittal segment orientation.
    """
    # research
    u.profprint()
    sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
    if sYellow is None:
        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
    reformatLogic = slicer.vtkSlicerReformatLogic()
    sYellow.SetSliceVisible(0)
    sYellow.SetOrientationToSagittal()
    sw = slicer.app.layoutManager().sliceWidget("Yellow")
    sw.fitSliceToBackground()
    sYellow.Modified()


def reformatCoronalView4NeedleSegment(base, tip, ID=-1):
    """
    Reformat the coronal view to be tangent to the needle.
    """
    # research
    u.profprint()
    for i in range(2):  # workaround update problem
        if ID >= 0:
            modelNode = slicer.util.getNode("vtkMRMLModelNode" + str(ID))
            polyData = modelNode.GetPolyData()
            nb = polyData.GetNumberOfPoints()
            base = [0, 0, 0]
            tip = [0, 0, 0]
            polyData.GetPoint(nb - 1, tip)
            polyData.GetPoint(0, base)
        a, b, c = tip[0] - base[0], tip[1] - base[1], tip[2] - base[2]

        sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        if sGreen is None:
            sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode3")
        reformatLogic = slicer.vtkSlicerReformatLogic()
        # sGreen.SetSliceVisible(1)
        reformatLogic.SetSliceNormal(sGreen, 1, -a / b, 0)
        # reformatLogic.SetSliceOrigin(sGreen, base[0],base[1],base[2])#crashes
        m = sGreen.GetSliceToRAS()
        m.SetElement(0, 3, base[0])
        m.SetElement(1, 3, base[1])
        m.SetElement(2, 3, base[2])
        sGreen.Modified()


def drawIsoSurfaces0(self):
    """
    DEPRECATED. for development purposes.
    This indicates radiation influence zones.
    Ellipsoid at tip of the needle.
    """
    # research
    u.profbox()
    modelNodes = slicer.util.getNodes("vtkMRMLModelNode*")
    v = vtk.vtkAppendPolyData()

    for modelNode in list(modelNodes.values()):
        if (
                modelNode.GetAttribute("nth") != None
                and modelNode.GetDisplayVisibility() == 1
        ):
            v.AddInput(modelNode.GetPolyData())

    modeller = vtk.vtkImplicitModeller()
    modeller.SetInput(v.GetOutput())
    modeller.SetSampleDimensions(self.dim.value, self.dim.value, self.dim.value)
    modeller.SetCapping(0)
    modeller.SetAdjustBounds(self.abonds.value)
    modeller.SetProcessModeToPerVoxel()
    modeller.SetAdjustDistance(self.adist.value / 100)
    modeller.SetMaximumDistance(self.maxdist.value / 100)

    contourFilter = vtk.vtkContourFilter()
    contourFilter.SetNumberOfContours(self.nb.value)
    contourFilter.SetInputConnection(modeller.GetOutputPort())
    contourFilter.ComputeNormalsOn()
    contourFilter.ComputeScalarsOn()
    contourFilter.UseScalarTreeOn()
    contourFilter.SetValue(self.contour.value, self.contourValue.value)
    contourFilter.SetValue(self.contour2.value, self.contourValue2.value)
    contourFilter.SetValue(self.contour3.value, self.contourValue3.value)
    contourFilter.SetValue(self.contour4.value, self.contourValue4.value)
    contourFilter.SetValue(self.contour5.value, self.contourValue5.value)

    isoSurface = contourFilter.GetOutput()
    self.AddContour(isoSurface)

def addRadiation(i, needleID):
    """
    Goal of this function is to draw quadratics, simulating the dose radiation.
    Currently, ellipse is a too naive model.
    This project might be continued later
    """
    # obsolete
    needleNode = slicer.mrmlScene.GetNodeByID(needleID)
    polyData = needleNode.GetPolyData()
    nb = polyData.GetNumberOfPoints()
    base = [0,0,0]
    tip = [[0,0,0] for k in range(11)]
    if nb>100:
        polyData.GetPoint(nb-1,tip[10])
        polyData.GetPoint(0,base)

    a = tip[10][0]-base[0]
    b = tip[10][1]-base[1]
    c = tip[10][2]-base[2]

    for l in range(7):
        tip[9-l][0] = tip[10][0]-0.1*a*(l+1)
        tip[9-l][1] = tip[10][1]-0.1*b*(l+1)
        tip[9-l][2] = tip[10][2]-0.1*c*(l+1)
    for l in range(1,3):
        tip[l][0] = tip[10][0]+0.1*a*l
        tip[l][1] = tip[10][1]+0.1*b*l
        tip[l][2] = tip[10][2]+0.1*c*l

    rad = vtk.vtkAppendPolyData()

    for l in range(1,11):
        TransformPolyDataFilter=vtk.vtkTransformPolyDataFilter()
        Transform=vtk.vtkTransform()
        TransformPolyDataFilter.SetInput(m_polyRadiation)

        vtkmat = Transform.GetMatrix()
        vtkmat.SetElement(0,3,tip[l][0])
        vtkmat.SetElement(1,3,tip[l][1])
        vtkmat.SetElement(2,3,tip[l][2])
        TransformPolyDataFilter.SetTransform(Transform)
        TransformPolyDataFilter.Update()

        rad.AddInput(TransformPolyDataFilter.GetOutput())

    modelNode = slicer.vtkMRMLModelNode()
    displayNode = slicer.vtkMRMLModelDisplayNode()
    storageNode = slicer.vtkMRMLModelStorageNode()

    fileName = 'Rad' + option[i] + '.vtk'

    mrmlScene = slicer.mrmlScene
    modelNode.SetName(fileName)
    modelNode.SetAttribute("radiation", "segmented")
    modelNode.SetAttribute("needleID", str(needleID))
    modelNode.SetAndObservePolyData(rad.GetOutput())

    modelNode.SetScene(mrmlScene)
    storageNode.SetScene(mrmlScene)
    storageNode.SetFileName(fileName)
    displayNode.SetScene(mrmlScene)
    displayNode.SetVisibility(0)
    mrmlScene.AddNode(storageNode)
    mrmlScene.AddNode(displayNode)
    mrmlScene.AddNode(modelNode)
    modelNode.SetAndObserveStorageNodeID(storageNode.GetID())
    modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())

    displayNode.SetPolyData(modelNode.GetPolyData())

    displayNode.SetSliceIntersectionVisibility(0)
    displayNode.SetScalarVisibility(1)
    displayNode.SetActiveScalarName('scalars')
    displayNode.SetScalarRange(0, 230)
    displayNode.SetOpacity(0.06)
    displayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileHotToColdRainbow.txt')
    displayNode.SetBackfaceCulling(0)
    pNode = parameterNode()
    pNode.SetParameter(fileName,modelNode.GetID())
    mrmlScene.AddNode(modelNode)