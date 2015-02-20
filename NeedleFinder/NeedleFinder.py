# -*- coding: utf-8 -*-
"""**NeedleFinder Documentation**

Guillaume Pernelle,  Andre Mastmeyer

.. moduleauthor:: gpernelle <gpernelle@gmail.com>

.. image:: https://raw.githubusercontent.com/gpernelle/NeedleFinder/amastm/docs/_static/algo-figure-high_res.png
           :height: 250px
           :width: 700 px
           :scale: 100 %
           :alt: alternate text
           :align: center

Links
-----
    * Validation of Catheter Segmentation for MR-guided Gynecologic Cancer Brachytherapy [1]_

    * Labeled Needle Rendering Solution for Image Guided Brachytherapy [2]_

  .. [1] https://www.spl.harvard.edu/publications/item/view/2459
  .. [2] https://www.spl.harvard.edu/publications/item/view/2316
"""
"""
TODO: gaussianAttenuation in NeedleDetectionThread is missing 1/(sigma*(2pi)**0.5)
meaning the integral of the gaussian is not always 1 - we could see the impact of adding the scaling effect by
redoing the parameter search with it.
"""

import unittest
import math, time, operator
import numpy
import numpy as np
import random
import csv
import ConfigParser
import inspect
import SimpleITK as sitk
import sitkUtils
import os.path
import time as t
import vtk, qt, ctk, slicer

import EditorLib
from EditorLib.EditUtil import EditUtil
from Editor import EditorWidget

def whoami():
    return inspect.stack()[1][3]
def whosdaddy():
    return inspect.stack()[2][3]
def whosgranny():
    return inspect.stack()[3][3]
def lineno():
    """Returns the current line number in our program."""
    return int(inspect.currentframe().f_back.f_lineno)
def pause():
  """
  Pause execution of program. You can use the viewers! Press enter in console...
  """
  #research
  try:
    input("Press enter to continue")
  except EOFError:
    pass

profiling = True
frequent = False
MAXNEEDLES = 205 # we have no more than 205 colors
conesColor=300 # color for visualizing the search cones (for debugging, None turns it off)

def msgbox(text):
  qt.QMessageBox.about(0, 'Profiling:', text)
  print text
def profprint(className=""):
  if profiling: print "%s.%s -----------------------" % (className, whosdaddy())
def profbox(className=""):  
  if profiling: strg = "%s.%s -----------------------" % (className, whosdaddy()); print strg; msgbox(strg)
if profiling: msgbox("turned on")
def getClassName(self):
  """
  return class name
  """
  return self.__class__.__name__
    
#
# NeedleFinder
#

class NeedleFinder:
  def __init__(self, parent):
    """
    init's the class
    """
    # productive
    profprint()
    parent.title = "NeedleFinder"
    parent.categories = ["IGT"]
    parent.dependencies = []
    parent.contributors = ["Guillaume Pernelle", "Andre Mastmeyer", "Alireza Mehrtash", "Lauren Barber", "Nabgha Fahrat", "Sandy Wells", "Yi Gao", "Antonio Damato", "Tina Kapur", "Akila Viswanathan"]
    parent.helpText = "https://github.com/gpernelle/NeedleFinder/wiki";
    parent.acknowledgementText = " Version : " + "NeedleFinder 2015 v1.0."
    self.NeedleFinderWidget = 0
    self.parent = parent
    try:
      slicer.selfTests
    except AttributeError:
      slicer.selfTests = {}
    slicer.selfTests['NeedleFinder'] = self.runTest

  def __del__(self):
    if self.NeedleFinderWidget:
      self.NeedleFinderWidget.removeObservers()

  def getName(self):
    """
    return class name
    """
    return self.__class__.__name__
  
  def runTest(self):
    """
    Unit testing 
    """
    # framework #testing
    profprint()
    tester = NeedleFinderTest()
    tester.runTest()

#
# NeedleFinderWidget
#

class NeedleFinderWidget:
  
  def __init__(self, parent=None):
    """
    init's the class
    """
    # productive
    profprint()
    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
    else:
      self.parent = parent
    self.layout2 = self.parent.layout()
    self.layout = qt.QFormLayout()
    if not parent:
      self.setup()
      self.parent.show()

    self.analysisGroupBox = None
    self.buttonsGroupBox = None
    self.interactorObserverTags = []    
    self.styleObserverTags = []
    self.axialSegmentationLimit = None
    self.templateSliceButton = None
    self.fiducialButton = None
    self.newInsertionButton = None
    self.deleteNeedleButton = None
    self.resetDetectionButton = None
    self.resetValidationButton = None
    # class var
    self.validationNeedleNumber = 1
    self.stepNeedle = 0
    self.fileName = None
    self.fileDialog = None
    self.dirDialog = None
    self.logic = NeedleFinderLogic() 
    self.needleValidationClicks = 1
    self.addManualTipClicks = 2
    self.obturatorNeedleTipClicks = 3

    # keep list of pairs: [observee,tag] so they can be removed easily
    self.styleObserverTags = []
    # keep a map of interactor styles to sliceWidgets so we can easily get sliceLogic
    self.sliceWidgetsPerStyle = {}
    # self.refreshObservers()

    self.CrosshairNode = None
    self.CrosshairNodeObserverTag = None

    # crosshairnode use to get mouse position
    self.CrosshairNode = slicer.mrmlScene.GetNthNodeByClass(0, 'vtkMRMLCrosshairNode')
    if self.CrosshairNode:
      self.CrosshairNodeObserverTag = self.CrosshairNode.AddObserver(slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, self.processEvent)
    
    # segmentation editor variables
    self.editorWidget = None
    self.editUtil = None
    self.undoRedo = None
    self.wandLogics = {}
    self.labelMapNode = None
    self.currentLabel = None
    self.tempPointList = []
    
  def __del__(self):
    self.removeObservers()

  def getName(self):
    """
    return class name
    """
    return self.__class__.__name__
  
  def createAddOrSelectLabelMapNode(self):
    """
    Create label map node for Segmentation editor and needle finder.
    """
    # productive
    profprint()
    print "creating label map for working intensity volume"
    # create, select label map
    volLogic = slicer.modules.volumes.logic()
    sliceLogic = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
    vn = sliceLogic.GetBackgroundLayer().GetVolumeNode()
    self.labelMapNode = slicer.util.getNode(vn.GetName() + "-label")
    if not self.labelMapNode:
      self.labelMapNode = volLogic.CreateAndAddLabelVolume(slicer.mrmlScene, vn, vn.GetName() + "-label")
    # select label volume
    selectionNode = slicer.app.applicationLogic().GetSelectionNode()
    selectionNode.SetReferenceActiveLabelVolumeID(self.labelMapNode.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection(0)
    self.editorWidget.setMasterNode(vn)
    self.editorWidget.setMergeNode(self.labelMapNode) 
  
  def onEditorCollapsed(self, collapsed):
    """
    When segmentation editor is used before needle finder, prepare a a label volume.
    """
    # productive
    profprint()
    if collapsed:
      pass
    else:
      self.createAddOrSelectLabelMapNode()

  def setup(self):
    """
    Instantiate and connect widgets
    """
    # productive
    profprint()
    #-----------------------------------------------------------------------------
    # Needle Finder Logic
    logic = self.logic

    #Report Frame########################################
    self.__reportFrame = ctk.ctkCollapsibleButton()
    self.__reportFrame.text = "Segmentation Report"
    self.__reportFrame.collapsed = 0
    reportFrame = qt.QFormLayout(self.__reportFrame)

    # segmentation report
    self.analysisGroupBox = qt.QGroupBox()
    self.analysisGroupBox.setFixedHeight(330)
    self.analysisGroupBox.setTitle('Segmentation Report')
    reportFrame.addRow(self.analysisGroupBox)
    self.analysisGroupBoxLayout = qt.QFormLayout(self.analysisGroupBox)

    #-----------------------------------------------------------------------------

    #Segmentation Frame##########################################
    self.__segmentationFrame = ctk.ctkCollapsibleButton()
    self.__segmentationFrame.text = "Segmentation"
    self.__segmentationFrame.collapsed = 0
    segmentationFrame = qt.QFormLayout(self.__segmentationFrame)

    # 1 Define template
    self.templateSliceButton = qt.QPushButton('1. Select Current Axial Slice as Seg. Limit (current: None)')
    segmentationFrame.addRow(self.templateSliceButton)
    self.templateSliceButton.connect('clicked()', logic.placeAxialLimitMarker)
    self.templateSliceButton.setEnabled(1)

    # 2 give needle tips
    self.fiducialButton = qt.QPushButton('2. Start Giving Needle Tips [CTRL + ENTER]')
    self.fiducialButton.checkable = True
    segmentationFrame.addRow(self.fiducialButton)
    self.fiducialButton.connect('toggled(bool)', self.onStartStopGivingNeedleTipsToggled)
    self.fiducialButton.setEnabled(0)

    # New insertion - create new set of needles with different colors
    self.newInsertionButton = None
    # self.newInsertionButton = qt.QPushButton('New Needle Set')
    # segmentationFrame.addRow(self.newInsertionButton)
    # self.newInsertionButton.connect('clicked()', logic.newInsertionNeedleSet)
    # self.newInsertionButton.setEnabled(0)

    # Delete Needle Button 
    self.deleteNeedleButton = qt.QPushButton('Delete Last Segmented Needle [Ctrl + Z]')
    segmentationFrame.addRow(self.deleteNeedleButton)
    # self.deleteNeedleButton.connect('clicked()', logic.deleteAllAutoNeedlesFromScene)
    self.deleteNeedleButton.connect('clicked()', logic.deleteLastNeedle)
    self.deleteNeedleButton.setEnabled(0)

    # Reset Needle Detection Button 
    self.resetDetectionButton = qt.QPushButton('Reset Needle Detection (Start Over)')
    segmentationFrame.addRow(self.resetDetectionButton)
    self.resetDetectionButton.connect('clicked()', logic.resetNeedleDetection)
    self.resetDetectionButton.setEnabled(0)

    #Validation Frame##########################################
    self.__validationFrame = ctk.ctkCollapsibleButton()
    self.__validationFrame.text = "Validation"
    self.__validationFrame.collapsed = 0 # <<<
    validationFrame = qt.QFormLayout(self.__validationFrame)

    self.startGivingControlPointsButton = qt.QPushButton('Start Giving Control Points')
    self.startGivingControlPointsButton.checkable = True
    validationFrame.addRow(self.startGivingControlPointsButton)
    self.startGivingControlPointsButton.connect('toggled(bool)', self.onStartStopGivingValidationControlPointsToggled)

    self.validationNeedleButton = qt.QPushButton('Next Validation Needle: (1)->(2)')
    self.validationNeedleButton.toolTip = "By clicking on this button, you will increment the number of the needle"
    self.validationNeedleButton.toolTip += "that you want to manually segment. Thus, the points you will add will be used to draw a new needle.<br/>"
    self.validationNeedleButton.toolTip += "<b>Warning:<b> You can/'t add any more points to the current needle after clicking here"
    validationFrame.addRow(self.validationNeedleButton)
    self.validationNeedleButton.connect('clicked()', logic.validationNeedle)

    self.drawValidationNeedlesButton = qt.QPushButton('Draw Needle 3D Models')
    self.drawValidationNeedlesButton.toolTip = "Redraw every manually segmented needles. This is usefull for example if you moved a control point, or after you added a new needle"
    validationFrame.addRow(self.drawValidationNeedlesButton)
    self.drawValidationNeedlesButton.connect('clicked()', logic.drawValidationNeedles)

    self.startValidationButton = qt.QPushButton('Start Evaluation')
    self.startValidationButton.toolTip = "Launch tracking algo. from the tip of the manually segmented needles"
    validationFrame.addRow(self.startValidationButton)
    self.startValidationButton.connect('clicked()', logic.startValidation)
    #self.startValidationButton.setStyleSheet("background-color: yellow")
    self.startValidationButton.setStyleSheet("background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f7f700, stop: 1 #dbdb00)");

    # Reset Needle Validation Button 
    self.resetValidationButton = qt.QPushButton('Reset Needles from Manual Segmentation')
    validationFrame.addRow(self.resetValidationButton)
    self.resetValidationButton.connect('clicked()', logic.resetNeedleValidation)

    self.editNeedleTxtBox = qt.QSpinBox()
    self.editNeedleTxtBox.connect("valueChanged(int)", logic.changeValue)
    editLabel = qt.QLabel('Choose Needle for Ctrl Pt scrolling:')
    validationFrame.addRow(editLabel, self.editNeedleTxtBox)

    self.scrollPointButton = qt.QPushButton('Scroll Ctrl Pt for Needle ' + str(self.editNeedleTxtBox.value))
    validationFrame.addRow(self.scrollPointButton)
    self.scrollPointButton.connect('clicked()', logic.scrollPoint)

    # Needle detection parameters#################################
    self.__parameterFrame = ctk.ctkCollapsibleButton()
    self.__parameterFrame.text = "Needle Detection Parameters (Developers)"
    self.__parameterFrame.collapsed = 1
    parameterFrame = qt.QFormLayout(self.__parameterFrame)
    
    # Load/Save/Reset
    self.configFrame = qt.QFrame()
    self.configFrame.setLayout(qt.QHBoxLayout())
    parameterFrame.layout().addRow(self.configFrame)
    self.loadButton = qt.QPushButton()
    self.loadButton.text = "Load Parameters"
    self.loadButton.checkable = False
    self.loadButton.toolTip = "Click to load parameters from a configuration file."
    self.loadButton.connect('clicked()', self.onLoad)
    self.saveButton = qt.QPushButton()
    self.saveButton.checkable = False
    self.saveButton.text = "Save Parameters"
    self.saveButton.toolTip = "Click to save the parameters in a configuration file."
    self.saveButton.connect('clicked()', self.onSave)
    self.resetParametersButton = qt.QPushButton()
    self.resetParametersButton.checkable = False
    self.resetParametersButton.text = "Reset Default Parameters"
    self.resetParametersButton.toolTip = "Click to reset the default parameters from default.cfg"
    self.resetParametersButton.connect('clicked()', self.onResetParameters)
    self.configFrame.layout().addWidget(self.loadButton)
    self.configFrame.layout().addWidget(self.saveButton)
    self.configFrame.layout().addWidget(self.resetParametersButton)

    # Auto correct tip position?
    self.autoCorrectTip = qt.QCheckBox('Auto correct tip position?')
    parameterFrame.addRow(self.autoCorrectTip)
    self.autoCorrectTip.setChecked(0)

    # Look for needles in CT?
    self.invertedContrast = qt.QCheckBox('Search for bright needles (CT)?')
    parameterFrame.addRow(self.invertedContrast)
    # Compute gradient?
    self.gradient = qt.QCheckBox('Compute gradient?')
    self.gradient.setChecked(1)
    parameterFrame.addRow(self.gradient)

    # Filter ControlPoints?
    self.filterControlPoints = qt.QCheckBox('Filter Control Points?')
    self.filterControlPoints.setChecked(0)
    # parameterFrame.addRow(self.filterControlPoints)

    # Draw Fiducial Points?
    self.drawFiducialPoints = qt.QCheckBox('Draw Control Points?')
    self.drawFiducialPoints.setChecked(0)
    parameterFrame.addRow(self.drawFiducialPoints)

    # Auto find Tips: Tracking in +z and -z direction
    self.autoStopTip = qt.QCheckBox('Tracking in both directions')
    self.autoStopTip.setChecked(0)
    parameterFrame.addRow(self.autoStopTip)

    # Extend Needle to the wanted value
    self.extendNeedle = qt.QCheckBox('Extend Needle')
    self.extendNeedle.setChecked(0)
    parameterFrame.addRow(self.extendNeedle)

    # Real Needle Value (used to extend the needle)
    realNeedleLengthLabel = qt.QLabel('Real Needle Length (mm):')
    self.realNeedleLength = qt.QSpinBox()
    self.realNeedleLength.setMinimum(0.1)
    self.realNeedleLength.setMaximum(1500)
    self.realNeedleLength.setValue(240)
    parameterFrame.addRow(realNeedleLengthLabel, self.realNeedleLength)

    # Max Needle Length?
    self.maxLength = qt.QCheckBox('Max Needle Length?')
    self.maxLength.setChecked(1)
    parameterFrame.addRow(self.maxLength)

    # Add Gaussian Estimation?
    self.gaussianAttenuationButton = qt.QCheckBox('Add Gaussian Prob. Attenuation?')
    self.gaussianAttenuationButton.setChecked(1)
    parameterFrame.addRow(self.gaussianAttenuationButton)

    # nb points per line spin box
    # ## previously 4 - try with 20
    self.sigmaValue = qt.QSpinBox()
    self.sigmaValue.setMinimum(0.1)
    self.sigmaValue.setMaximum(500)
    self.sigmaValue.setValue(20)
    sigmaValueLabel = qt.QLabel("Sigma Value (exp(-x^2/(2*(sigma/10)^2))): ")
    parameterFrame.addRow(sigmaValueLabel, self.sigmaValue)

    # nb points per line spin box
    self.gradientPonderation = qt.QSpinBox()
    self.gradientPonderation.setMinimum(0.01)
    self.gradientPonderation.setMaximum(500)
    self.gradientPonderation.setValue(5)
    gradientPonderationLabel = qt.QLabel("Gradient Ponderation: ")
    parameterFrame.addRow(gradientPonderationLabel, self.gradientPonderation)

    # center accuentuation
    # ## previously 1, try with 2 ( avoids exiting catheter track)
    self.exponent = qt.QSpinBox()
    self.exponent.setMinimum(0.01)
    self.exponent.setMaximum(500)
    self.exponent.setValue(2)
    exponentLabel = qt.QLabel("Center Ponderation: ")
    parameterFrame.addRow(exponentLabel, self.exponent)

    # nb points per line spin box
    self.nbPointsPerLine = qt.QSpinBox()
    self.nbPointsPerLine.setMinimum(2)
    self.nbPointsPerLine.setMaximum(500)
    self.nbPointsPerLine.setValue(20)
    nbPointsPerLineLabel = qt.QLabel("Number of points per line: ")
    # parameterFrame.addRow( nbPointsPerLineLabel, self.nbPointsPerLine)

    # nb radius iteration spin box
    self.nbRadiusIterations = qt.QSpinBox()
    self.nbRadiusIterations.setMinimum(2)
    self.nbRadiusIterations.setMaximum(1000)
    self.nbRadiusIterations.setValue(13)
    nbRadiusIterationsLabel = qt.QLabel("Number of distance iterations: ")
    # parameterFrame.addRow( nbRadiusIterationsLabel, self.nbRadiusIterations)
    
    # distance max spin box
    self.radiusMax = qt.QSpinBox()
    self.radiusMax.setMinimum(0)
    self.radiusMax.setMaximum(1000)
    self.radiusMax.setValue(5)
    distanceMaxLabel = qt.QLabel("Radius of cone base (mm): ")
    parameterFrame.addRow(distanceMaxLabel, self.radiusMax)
    
    # nb rotating iterations spin box
    self.nbRotatingIterations = qt.QSpinBox()
    self.nbRotatingIterations.setMinimum(2)
    self.nbRotatingIterations.setMaximum(1000)
    self.nbRotatingIterations.setValue(35)
    nbRotatingIterationsLabel = qt.QLabel("Number of rotating steps: ")
    parameterFrame.addRow(nbRotatingIterationsLabel, self.nbRotatingIterations)
    
    # nb heights per needle spin box
    self.numberOfPointsPerNeedle = qt.QSpinBox()
    self.numberOfPointsPerNeedle.setMinimum(1)
    self.numberOfPointsPerNeedle.setMaximum(50)
    self.numberOfPointsPerNeedle.setValue(6)
    numberOfPointsPerNeedleLabel = qt.QLabel("Number of Control Points: ")
    parameterFrame.addRow(numberOfPointsPerNeedleLabel, self.numberOfPointsPerNeedle)
    
    # nb heights per needle spin box
    self.stepsize = qt.QSpinBox()
    self.stepsize.setMinimum(1)
    self.stepsize.setMaximum(500)
    self.stepsize.setValue(5)
    stepsizeLabel = qt.QLabel("Stepsize: ")
    # parameterFrame.addRow( stepsizeLabel, self.stepsize)

    # lenghtNeedle
    self.lenghtNeedleParameter = qt.QSpinBox()
    self.lenghtNeedleParameter.setMinimum(1)
    self.lenghtNeedleParameter.setMaximum(10000)
    self.lenghtNeedleParameter.setValue(100)
    stepsizeLabel = qt.QLabel("Lenght of the needles (mm): ")
    parameterFrame.addRow(stepsizeLabel, self.lenghtNeedleParameter)

    # radius
    self.radiusNeedleParameter = qt.QSpinBox()
    self.radiusNeedleParameter.setMinimum(1)
    self.radiusNeedleParameter.setMaximum(200)
    self.radiusNeedleParameter.setValue(2)
    radiusLabel = qt.QLabel("Radius of the needles (mm): ")
    parameterFrame.addRow(radiusLabel, self.radiusNeedleParameter)
    
    # algo
    self.algoVersParameter = qt.QSpinBox()
    self.algoVersParameter.setMinimum(0)
    self.algoVersParameter.setMaximum(3)
    self.algoVersParameter.setValue(0)
    algoLabel = qt.QLabel("Needle detection version: ")
    parameterFrame.addRow(algoLabel, self.algoVersParameter)
    
    # Research/dev. area#################################
    self.__devFrame = ctk.ctkCollapsibleButton()
    self.__devFrame.text = "R&&D (Developers)"
    self.__devFrame.collapsed = 1
    devFrame = qt.QFormLayout(self.__devFrame)

    # #Segment Needle Button 
    # self.needleButton = qt.QPushButton('Segment Needles')
    # segmentationFrame.addRow(self.needleButton)
    # self.needleButton.connect('clicked()', self.needleSegmentation)
    # self.needleButton.setEnabled(0)

    # Segment Needle Button 
    # self.needleButton2 = qt.QPushButton('Segment/Update Needles - Python')
    # segmentationFrame.addRow(self.needleButton2)
    # self.needleButton2.connect('clicked()', self.needleDetection)

    # Obturator needle tips
    self.fiducialObturatorButton = qt.QPushButton('Start Giving Obturator Needle Tips')
    self.fiducialObturatorButton.checkable = True
    self.fiducialObturatorButton.connect('toggled(bool)', self.onStartStopGivingObturatorNeedleTipsToggled)

    self.displayFiducialButton = qt.QPushButton('Display Labels On Needles')
    self.displayFiducialButton.connect('clicked()', logic.displayFiducial)
    
    self.displayContourButton = qt.QPushButton('Draw Radiation Isosurfaces')
    self.displayContourButton.checkable = False
    self.displayContourButton.connect('clicked()', logic.drawIsoSurfaces)
    
    self.hideContourButton = qt.QPushButton('Hide Radiation Isosurfaces')
    self.hideContourButton.checkable = True
    self.hideContourButton.connect('clicked()', logic.hideIsoSurfaces)
    self.hideContourButton.setEnabled(0)
    
    self.filterButton = qt.QPushButton('Preprocessing')
    self.filterButton.checkable = False
    self.filterButton.connect('clicked()', logic.filterWithSITK)
    self.filterButton.setEnabled(1)
    
    self.parSearchButton = qt.QPushButton('Parameter Search')
    self.parSearchButton.checkable = False
    self.parSearchButton.connect('clicked()', logic.parSearch)
    self.parSearchButton.setEnabled(1)
    
    self.setAsValNeedlesButton = qt.QPushButton('Use Needles for Validation')
    self.setAsValNeedlesButton.checkable = False
    self.setAsValNeedlesButton.connect('clicked()', logic.setAllNeedleTubesAsValidationNeedles)
    self.setAsValNeedlesButton.setEnabled(1)
    self.setAsValNeedlesButton.setStyleSheet("background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f7f700, stop: 1 #dbdb00)");
    
    # ## create segmentation editor environment:
    editorWidgetParent = slicer.qMRMLWidget()
    editorWidgetParent.setLayout(qt.QVBoxLayout())
    editorWidgetParent.setMRMLScene(slicer.mrmlScene)
    editorWidgetParent.hide()
    self.editorWidget = None
    # The order of statements is important here for resetNeedleDetection to work!!
    self.editorWidget = EditorWidget(editorWidgetParent, False)
    self.editUtil = None
    self.editUtil = self.editorWidget.editUtil  # EditorLib.EditUtil.EditUtil()
    self.currentLabel = None
    self.setWandEffectOptions()  # has to be done before setup():
    self.editUtil.setCurrentEffect("DefaultTool")
    self.editorWidget.setup()
    # our mouse mode button
    self.editorWidget.toolsBox.actions["NeedleFinder"] = qt.QAction(0)  # dummy self.fiducialButton
    self.undoRedo = None
    self.undoRedo = self.editorWidget.toolsBox.undoRedo
    self.currentLabel = self.editUtil.getLabel()
    self.editorWidget.editLabelMapsFrame.setText("Edit Segmentation")
    self.editorWidget.editLabelMapsFrame.connect('contentsCollapsed(bool)', self.onEditorCollapsed)
    editorWidgetParent.show()
    self.editUtil.setCurrentEffect("NeedleFinder")
  
    # devFrame.addRow(self.displayFiducialButton)
    devFrame.addWidget(editorWidgetParent)
    devFrame.addRow(self.fiducialObturatorButton)
    devFrame.addRow(self.displayContourButton)
    devFrame.addRow(self.hideContourButton)
    devFrame.addRow(self.filterButton)
    devFrame.addRow(self.parSearchButton)
    devFrame.addRow(self.setAsValNeedlesButton)
    
    #put frames on the tab########################################
    self.layout.addRow(self.__segmentationFrame)
    self.layout.addRow(self.__reportFrame)
    self.layout.addRow(self.__validationFrame)
    self.layout.addRow(self.__parameterFrame)
    self.layout.addRow(self.__devFrame)
    
    # reset module
    resetButton = qt.QPushButton('Reset Module')
    resetButton.connect('clicked()', self.onReload)
    self.widget = slicer.qMRMLWidget()
    self.widget.setLayout(self.layout)
    self.layout2.addWidget(self.widget)

    # init table report
    logic.initTableView()  # init the report table
    
    # Lauren's feature request: set mainly unused coronal view to sagittal to display ground truth bitmap image (if available)
    # Usage after fresh slicer start: 1. Load scene and 2. reference jpg. 3. Then open NeedleFinder from Modules selector
    vnJPG = slicer.util.getNode("Case *")  # the naming convention for the ground truth JPG files: "Case XXX.jpg"
    if vnJPG:
      print "showing ground 2d image truth in green view"
      # show JPG image if available
      sw = slicer.app.layoutManager().sliceWidget("Green")
      cn = sw.mrmlSliceCompositeNode()
      cn.SetBackgroundVolumeID(vnJPG.GetID())
      slicer.app.layoutManager().sliceWidget("Green").sliceLogic().GetBackgroundLayer().Modified()
      sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
      if sGreen == None :
        sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
      # set to axial view
      sGreen.SetSliceVisible(0)
      sGreen.SetOrientationToAxial()
      sw.fitSliceToBackground()
      sGreen.Modified()
 
    self.onResetParameters()
    self.setupShortcuts()
    
  def setWandEffectOptions(self, tolerance=20, maxPixels=50, fillMode="Volume"):
    """
    Set the wand logic parameters in parameter node
    """
    # research
    profprint()
    parameterNode = self.editUtil.getParameterNode()
    # set options 
    parameterNode.SetParameter("WandEffect,tolerance", str(tolerance))
    parameterNode.SetParameter("WandEffect,maxPixels", str(maxPixels))
    parameterNode.SetParameter("WandEffect,fillMode", fillMode)
    wandOpt = EditorLib.WandEffectOptions()
    wandOpt.setMRMLDefaults()
    wandOpt.__del__()
    
  def keyPressEvent(self, event):
    print "You Pressed: " + event.text()

  def setupShortcuts(self):
    """
    Set up hot keys for various actions.
    """
    # productive
    profprint()
    macros = (
      ("Ctrl+Return", self.segmentNeedle),
      ("Ctrl+z", self.logic.deleteLastNeedle),
      )

    for keys, f in macros:
      k = qt.QKeySequence(keys)
      s = qt.QShortcut(k, slicer.util.mainWindow())
      s.connect('activated()', f)
      s.connect('activatedAmbiguously()', f)
      print "'%s' -> '%s'" % (keys, f.__name__)
      # convenient for the python console
      globals()['nfw'] = nfw = slicer.modules.NeedleFinderWidget
      globals()['nfl'] = nfl = slicer.modules.NeedleFinderWidget.logic
      print "nfl -> NeedleFinderLogic"
      print "nfw -> NeedleFinderWidget"

  def segmentNeedle(self):
      """
      helper function for Ctrl+Enter
      """
      # productive #event
      profprint()
      if self.fiducialButton.isEnabled():
        print "new checked state: ", not self.fiducialButton.checked
        self.onStartStopGivingNeedleTipsToggled(not self.fiducialButton.checked)

  def cleanup(self):
    """
    clean up memory
    """
    # productive
    profprint()
    self.logic.resetNeedleDetection()
    self.logic.resetNeedleValidation()
    pass

  def refreshObservers(self):
    """ When the layout changes, drop the observers from
    all the old widgets and create new observers for the
    newly created widgets"""
    profprint()
    self.removeObservers()
    # get new slice nodes
    layoutManager = slicer.app.layoutManager()
    sliceNodeCount = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLSliceNode')
    for nodeIndex in xrange(sliceNodeCount):
      # find the widget for each node in scene
      sliceNode = slicer.mrmlScene.GetNthNodeByClass(nodeIndex, 'vtkMRMLSliceNode')
      sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())
      if sliceWidget:
        # add obserservers and keep track of tags
        style = sliceWidget.sliceView().interactorStyle()
        self.sliceWidgetsPerStyle[style] = sliceWidget
        # events = ("MouseMoveEvent", "EnterEvent", "LeaveEvent")
        events = ("LeftButtonPressEvent", "RightButtonPressEvent" "KeyPressEvent", "KeyReleaseEvent")
        for event in events:
          tag = style.AddObserver(event, self.processEvent)
          self.styleObserverTags.append([style, tag])
      # TODO: also observe the slice nodes

  def onReload(self, moduleName="NeedleFinder"):
    """
    Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    if profiling : profbox()
    # framework
    globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)

  def onReloadAndTest(self, moduleName="NeedleFinder"):
    """
    Generic reload method for any scripted module.
    ModuleWizard will subsitute correct default moduleName.
    """
    print "onReloadAndTest"; msgbox(whoami())
    try:
      self.onReload()
      evalString = 'globals()["%s"].%sTest()' % (moduleName, moduleName)
      tester = eval(evalString)
      tester.runTest()
    except Exception, e:
      import traceback
      traceback.print_exc()
      qt.QMessageBox.warning(slicer.util.mainWindow(),
          "Reload and Test", 'Exception!\n\n' + str(e) + "\n\nSee Python Console for Stack Trace")

  def onStartStopGivingNeedleTipsToggled(self, checked=True):
    """
    Start/stop giving needle tips
    """
    # productive
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    self.fiducialButton.checked = checked
    if checked:
      self.startGivingControlPointsButton.checked = 0
      self.fiducialObturatorButton.checked = 0
      self.start()
      self.fiducialButton.text = "2. Stop Giving Needle Tips [CTRL + ENTER]"
      widget.editUtil.setCurrentEffect("NeedleFinder")
    else:
      self.stop()
      self.fiducialButton.text = "2. Start Giving Needle Tips [CTRL + ENTER]"
      widget.editUtil.setCurrentEffect("DefaultTool")
      widget.resetDetectionButton.setEnabled(1)
      tempFidNodes = slicer.mrmlScene.GetNodesByName('Temp')
      for i in range(tempFidNodes.GetNumberOfItems()):
        node = tempFidNodes.GetItemAsObject(i)
        if node:
          slicer.mrmlScene.RemoveNode(node)
    widget.deleteNeedleButton.setEnabled(1)

  def onStartStopGivingObturatorNeedleTipsToggled(self, checked):
    """
    Start/stop giving obturator needle tips
    """
    # deprecated
    profprint()
    if checked:
      self.fiducialButton.checked = 0
      self.fiducialButton.text = "2. Start Giving Needle Tips [CTRL + ENTER]"
      self.startGivingControlPointsButton.checked = 0
      self.start(self.obturatorNeedleTipClicks)
      self.fiducialObturatorButton.text = "Stop Giving Obturator Needle Tips"  
    else:
      self.stop()
      self.fiducialObturatorButton.text = "Start Giving Obturator Needle Tips"

  def onStartStopGivingValidationControlPointsToggled(self, checked):
    """
    Start/stop needle validation control points. When checked is true, the mouse clicks are observed and leads to an action
    (here a new control point for a validation needle)
    """
    # productive
    profprint()
    if checked:
      self.fiducialObturatorButton.checked = 0
      self.fiducialButton.checked = 0
      self.fiducialButton.text = "2. Start Giving Needle Tips [CTRL + ENTER]"
      self.start(self.needleValidationClicks)
      self.startGivingControlPointsButton.text = "Stop Giving Control Points"  
    else:
      self.stop()
      self.startGivingControlPointsButton.text = "Start Giving Control Points"

  def start(self, process=0):
    """
    Start to observe the mouse clicks given by user (clicks on needle tips)
    """   
    # productive
    profprint()
    logic = self.logic
    logic.changeCursor(1)
    self.removeObservers()
    # get new slice nodes
    layoutManager = slicer.app.layoutManager()
    sliceNodeCount = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLSliceNode')
    for nodeIndex in xrange(sliceNodeCount):
      # find the widget for each node in scene
      sliceNode = slicer.mrmlScene.GetNthNodeByClass(nodeIndex, 'vtkMRMLSliceNode')
      sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())      
      if sliceWidget:     
        # add obserservers and keep track of tags
        style = sliceWidget.sliceView().interactorStyle()
        self.sliceWidgetsPerStyle[style] = sliceWidget
        events = ("LeftButtonPressEvent", "RightButtonPressEvent", "EnterEvent", "LeaveEvent", "KeyPressEvent", "KeyReleaseEvent")
        for event in events:
          if process == self.needleValidationClicks:
            tag = style.AddObserver(event, self.processEventNeedleValidation)
          elif process == self.addManualTipClicks:
            tag = style.AddObserver(event, self.processEventAddManualTips)
          elif process == self.obturatorNeedleTipClicks:
            tag = style.AddObserver(event, self.processEventAddObturatorNeedleTips)
            dn = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode().GetDisplayNode()
            w = dn.GetWindow()
            l = dn.GetLevel()
            dn.AddObserver(vtk.vtkCommand.ModifiedEvent, lambda c, e : logic.setWL(dn, w, l))
          else:
            tag = style.AddObserver(event, self.processEvent)   
          self.styleObserverTags.append([style, tag])

  def stop(self):
    """
    Stop to observe the mouse clicks given by user
    """
    # productive
    profprint()
    self.logic.changeCursor(0)
    self.removeObservers()
    self.fiducialObturatorButton.checked = 0
    self.fiducialButton.checked = 0
    self.validationNeedleButton.checked = 0

  def removeObservers(self):
    """
    Remove observers and reset
    """
    # productive #framework
    profprint()
    for observee, tag in self.styleObserverTags:
      observee.RemoveObserver(tag)
    self.styleObserverTags = []
    self.sliceWidgetsPerStyle = {}

  def processEvent(self, observee, event=None):
    """
    Observe events in the needle segmentation mode:
    - a mouse click starts a needle segmentation from the position of the cursor
    - if shift is released, a temporary fiducial node is created at the position of the cursor
    - if shift is pressed, all the temporary fiducial node named 'Temp' are removed from the MRML scence
    """
    # productive #frequent #event-handler
    if frequent: profprint();
    # print event
    widget = slicer.modules.NeedleFinderWidget
    # GET mouse position
    insideView = False
    ras = [0.0, 0.0, 0.0]
    xyz = [0.0, 0.0, 0.0]
    sliceNode = None
    if self.CrosshairNode:
      insideView = self.CrosshairNode.GetCursorPositionRAS(ras)
      sliceNode = self.CrosshairNode.GetCursorPositionXYZ(xyz)

    if self.sliceWidgetsPerStyle.has_key(observee):
      sliceWidget = self.sliceWidgetsPerStyle[observee]
      sliceLogic = sliceWidget.sliceLogic()
      sliceNode = sliceWidget.mrmlSliceNode()
      interactor = observee.GetInteractor()
      key = interactor.GetKeySym()
      # print "Event : ", event
      if 0:
        if event == "KeyPressEvent":  # shift pressed
          print 'key pressed: ', key
          if key == 'Shift_L' or key == 'Shift_R':
            tempFidNodes = slicer.mrmlScene.GetNodesByName('Temp')
            for i in range(tempFidNodes.GetNumberOfItems()):
              node = tempFidNodes.GetItemAsObject(i)
              if node:
                slicer.mrmlScene.RemoveNode(node)

        elif event == "KeyReleaseEvent":  # shift release
          print 'key released: ', key
          if key == 'Shift_L' or key == 'Shift_R':
            fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
            fiducial.SetName('Temp')
            fiducial.Initialize(slicer.mrmlScene)
            fiducial.SetFiducialCoordinates(ras)
            fiducial.SetAttribute('TemporaryFiducial', '1')
            fiducial.SetLocked(True)
            displayNode = fiducial.GetDisplayNode()
            displayNode.SetGlyphScale(2)
            displayNode.SetColor(1, 1, 0)
            textNode = fiducial.GetAnnotationTextDisplayNode()
            textNode.SetTextScale(4)
            textNode.SetColor(1, 1, 0)

      if event == "KeyReleaseEvent" and key == 'Shift_L' or key == 'Shift_R':
        # print event
        tempFidNodes = slicer.mrmlScene.GetNodesByName('Temp')
        # if fiducial exists, move it to new location
        if tempFidNodes.GetNumberOfItems() > 0:
          for i in range(tempFidNodes.GetNumberOfItems()):
                node = tempFidNodes.GetItemAsObject(i)
                if node:
                  node.SetFiducialCoordinates(ras)
                  self.tempPointList.append(ras)  # [0],ras[1],ras[2])
                  print "tempPointList: ", self.tempPointList
                if not self.wandLogics.has_key(sliceLogic):
                  if not self.labelMapNode:
                    self.createAddOrSelectLabelMapNode()
                  print "creating new segment logic"
                  wl = EditorLib.WandEffectLogic(sliceLogic)
                  wl.undoRedo = self.undoRedo
                  wl.editUtil = self.editUtil
                  self.wandLogics[sliceLogic] = wl
                print "wanding"
                self.setWandEffectOptions()  # !! the parameter node can be altered/deleted from outside so re-create/reset option node
                wl = self.wandLogics[sliceLogic]
                xy = interactor.GetEventPosition()
                print "xy: ", xy
                if wl.labelAtXY(xy):
                  self.editUtil.setLabel(wl.labelAtXY(xy))
                else:
                  print "new label"
                  self.currentLabel += 1
                  self.editUtil.setLabel(self.currentLabel)
                self.wandLogics[sliceLogic].apply(xy)
        else:  # create temp fiducial
          fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
          fiducial.SetName('Temp')
          fiducial.Initialize(slicer.mrmlScene)
          fiducial.SetFiducialCoordinates(ras)
          fiducial.SetAttribute('TemporaryFiducial', '1')
          fiducial.SetLocked(True)
          displayNode = fiducial.GetDisplayNode()
          displayNode.SetGlyphScale(2)
          displayNode.SetColor(1, 1, 0)
          textNode = fiducial.GetAnnotationTextDisplayNode()
          textNode.SetTextScale(4)
          textNode.SetColor(1, 1, 0)

      elif event == "LeftButtonPressEvent":  # mouse click
        # print event
        self.logic.t0 = time.clock()
        colorVar = random.randrange(50, 100, 1)  # ???/(100.)
        volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
        imageData = volumeNode.GetImageData()
        spacing = volumeNode.GetSpacing()
        ijk = self.logic.ras2ijk(ras)
        self.logic.needleDetectionThread(ijk, imageData, colorVar, spacing)
        if self.autoStopTip.isChecked():
          self.logic.needleDetectionUPThread(ijk, imageData, colorVar, spacing)
        # change requested by Lauren: remove temp marker after detection
        print "deleting temp marker and segmentation"
        tempFidNodes = slicer.mrmlScene.GetNodesByName('Temp')
        for i in range(tempFidNodes.GetNumberOfItems()):
          node = tempFidNodes.GetItemAsObject(i)
          if node:
            slicer.mrmlScene.RemoveNode(node)
        self.tempPointList = []
        # self.labelMapNode=None
        # clear label image
        if self.labelMapNode:
          if 0: self.clearLabelMap()
          
  def clearLabelMap(self,label=None):
    """
    Erase the contents of the label map.
    """
    # productive
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    print "clearing label map"
    self.undoRedo.saveState()
    labelImage = self.labelMapNode.GetImageData()
    shape = list(labelImage.GetDimensions()).reverse()
    labelArray = vtk.util.numpy_support.vtk_to_numpy(labelImage.GetPointData().GetScalars()).reshape(shape)
    if not label:
      labelArray[:] = 0
    else:
      labelArray[labelArray==label]=0
    self.editUtil.markVolumeNodeAsModified(widget.labelMapNode)

  def processEventNeedleValidation(self, observee, event=None):
    """
    Get the mouse clicks and create a fiducial node at this position. 
    """
    # productive #frequent #event-handler
    if frequent: profprint();
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision <= 21022:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        style = sliceWidget.sliceView().interactorStyle()          
        xy = style.GetInteractor().GetEventPosition()
        xyz = sliceWidget.convertDeviceToXYZ(xy)
        ras = sliceWidget.convertXYZToRAS(xyz)
      else:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        sliceLogic = sliceWidget.sliceLogic()
        sliceNode = sliceWidget.mrmlSliceNode()
        interactor = observee.GetInteractor()
        xy = interactor.GetEventPosition()
        xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy);
        ras = sliceWidget.sliceView().convertXYZToRAS(xyz)
      
      colorVar = random.randrange(50, 100, 1)  # ???/(100.)
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      ijk = self.logic.ras2ijk(ras)
      
      self.logic.t0 = time.clock()
      slicer.modules.NeedleFinderWidget.stepNeedle += 1
      self.logic.placeNeedleShaftEvalMarker(ijk, imageData, colorVar, spacing)

    # if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeaveEvent":
      # self.stop()

  def processEventAddObturatorNeedleTips(self, observee, event=None):
    """
    Get the mouse clicks and create a fiducial node at this position. 
    """
    # productive
    profprint()
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision <= 21022:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        style = sliceWidget.sliceView().interactorStyle()          
        xy = style.GetInteractor().GetEventPosition()
        xyz = sliceWidget.convertDeviceToXYZ(xy)
        ras = sliceWidget.convertXYZToRAS(xyz)
      else:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        sliceLogic = sliceWidget.sliceLogic()
        sliceNode = sliceWidget.mrmlSliceNode()
        interactor = observee.GetInteractor()
        xy = interactor.GetEventPosition()
        xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy);
        ras = sliceWidget.sliceView().convertXYZToRAS(xyz)
      
      colorVar = random.randrange(50, 100, 1)  # ???/(100.)
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      ijk = self.logic.ras2ijk(ras)
      self.logic.t0 = time.clock()
      self.logic.obturatorNeedle(ijk, imageData, colorVar, spacing)
      self.logic.obtuNeedle += 1

    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeaveEvent":
      self.stop()

  def processEventAddManualTips(self, observee, event=None):
    """
    Get the mouse clicks and create a fiducial node at this position. Used later for the fiducial registration
    ??? used?
    """
    # obsolete?
    profbox()
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision <= 21022:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        style = sliceWidget.sliceView().interactorStyle()          
        xy = style.GetInteractor().GetEventPosition()
        xyz = sliceWidget.convertDeviceToXYZ(xy)
        ras = sliceWidget.convertXYZToRAS(xyz)
      else:
        sliceWidget = self.sliceWidgetsPerStyle[observee]
        sliceLogic = sliceWidget.sliceLogic()
        sliceNode = sliceWidget.mrmlSliceNode()
        interactor = observee.GetInteractor()
        xy = interactor.GetEventPosition()
        xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy);
        ras = sliceWidget.sliceView().convertXYZToRAS(xyz)
      
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      # ijk=self.ras2ijk(ras)
      # self.t0=time.clock()
      self.logic.addManualTip(ras)

  def onSave(self):
    """
    show file dialog to save parameters
    """
    # productive #onButton
    profprint()
    
    self.fileDialog = qt.QFileDialog(self.parent)
    self.fileDialog.setDirectory(slicer.modules.needlefinder.path.replace("NeedleFinder.py", "Config"))
    self.fileDialog.options = self.fileDialog.DontUseNativeDialog
    self.fileDialog.acceptMode = self.fileDialog.AcceptSave
    self.fileDialog.defaultSuffix = "cfg"
    self.fileDialog.setNameFilter("Configuration file (*.cfg)")
    self.fileDialog.connect("fileSelected(QString)", self.saveFileSelected)
    self.fileDialog.show()

  def saveFileSelected(self, fileName):
    """
    save parameters
    """
    # productive #callback
    profprint()
    self.logic.saveParameters(fileName)

  def onLoad (self):
    """
    show file dialogue to load parameter file
    """
    # productive #onButton
    profprint()
    self.fileDialog = qt.QFileDialog(self.parent)
    self.fileDialog.setDirectory(slicer.modules.needlefinder.path.replace("NeedleFinder.py", "Config"))
    self.fileDialog.options = self.fileDialog.DontUseNativeDialog
    self.fileDialog.acceptMode = self.fileDialog.AcceptOpen
    self.fileDialog.defaultSuffix = "cfg"
    self.fileDialog.setNameFilter("Configuration File (*.cfg)")
    self.fileDialog.connect("fileSelected(QString)", self.onLoadFileSelected)
    self.fileDialog.show()

  def onLoadFileSelected(self, fileName):
    """
    load parameters
    """
    # productive #button
    profprint()
    self.logic.loadParameters(fileName)

  def onResetParameters(self):
    """
    load default parameter file
    """
    # productive #button
    profprint()
    fileName = pathToScene = slicer.modules.needlefinder.path.replace("NeedleFinder.py", "Config/default.cfg")
    self.logic.loadParameters(fileName)    

"""

########################################################################################################################
NEEDLEFINDER LOGIC
########################################################################################################################

"""

class NeedleFinderLogic:
  """
  This class implements all the actual
  computation done by the module.  The interface
  is such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget
  """
  # productive

  def __init__(self):
    """
    init's the class
    """
    # productive
    profprint()
    # initialisation of global variables
    self.option = self.setLabels()
    self.color = self.setColors()
    self.color255 = self.setColors255()
    self.p = self.setHolesCoordinates()
    self.t0 = 0
    self.obtuNeedle = 0
    self.row = 0
    self.col = 0
    self.round = 1
    self.fiducialNode = None
    # widget.stepNeedle         = 0
    self.ptNumber = 0
    self.table = None
    self.view = None
    self.model = None
    self.contourNode = None
    self.lastNeedleNames = []
    self.enableScreenshots = 0
    self.screenshotScaleFactor = 1

    self.previousValues = [[0, 0, 0]]
    self.tableValueCtrPt = [[[999, 999, 999] for i in range(100)] for j in range(100)]
    self.obtuNeedleValueCtrPt = [[[999, 999, 999] for i in range(10)] for j in range(10)]
    self.obtuNeedlePt = [[[999, 999, 999] for i in range(10)] for j in range(10)]
  
  def getName(self):
    """
    return class name
    """
    return self.__class__.__name__

  def hasImageData(self, volumeNode):
    """ Test:
    This is a dummy logic method that
    returns true if the passed in volume
    node has valid image data
    """
    # test
    profprint()
    if not volumeNode:
      print('no volume node')
      return False
    if volumeNode.GetImageData() == None:
      print('no image data')
      return False
    return True

  def delayDisplay(self, message, msec=1000):
    """ Test:
    logic version of delay display
    """
    profprint()
    # test
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message, self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def takeScreenshot(self, name, description, type=-1, annotate=True):
    """
    show the message even if not taking a screen shot
    ??? used?
    """
    # framework? #test
    profbox()
    self.delayDisplay(description)

    if self.enableScreenshots == 0:
      return

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == -1:
      # full window
      widget = slicer.util.mainWindow()
    elif type == slicer.qMRMLScreenShotDialog().FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog().ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog().Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog().Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog().Green:
      # green slice window
      widget = lm.sliceWidget("Green")

    # grab and convert to vtk image data
    qpixMap = qt.QPixmap().grabWidget(widget)
    qimage = qpixMap.toImage()
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage, imageData)
    
    if annotate == True:
      annotationLogic = slicer.modules.annotations.logic()
      annotationLogic.CreateSnapShot(name, description, type, self.screenshotScaleFactor, imageData)

  def run(self, inputVolume, outputVolume, enableScreenshots=0, screenshotScaleFactor=1):
    """
    Test: Run the actual algorithm
    """
    # test
    profprint()
    self.delayDisplay('Running the aglorithm')

    self.enableScreenshots = enableScreenshots
    self.screenshotScaleFactor = screenshotScaleFactor

    self.takeScreenshot('NeedleFinder-Start', 'Start', -1)

    return True

  def drawIsoSurfaces(self):
    """ Draw isosurfaces from models of the visible needles only.
    This shall indicate radiation influence zones.
    """
    # research
    profprint()

    slicer.modules.NeedleFinderWidget.hideContourButton.setEnabled(1)
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
       
    v = vtk.vtkAppendPolyData()
    canContinue = 0
    for modelNode in modelNodes.values():
      print "for"
      if modelNode.GetAttribute("nth") != None and modelNode.GetDisplayVisibility() == 1 :
        canContinue = 1
        v.AddInputData(modelNode.GetPolyData())
       
    if canContinue == 1:
      modeller = vtk.vtkImplicitModeller()
      modeller.SetInputConnection(v.GetOutputPort())
      modeller.SetSampleDimensions(60, 60, 60)
      modeller.SetCapping(0)
      modeller.AdjustBoundsOn()
      modeller.SetProcessModeToPerVoxel() 
      modeller.SetAdjustDistance(1)
      modeller.SetMaximumDistance(1.0)
      modeller.Update()
      
      contourFilter = vtk.vtkContourFilter()
      contourFilter.SetNumberOfContours(1)
      contourFilter.SetInputConnection(modeller.GetOutputPort())    
      contourFilter.ComputeNormalsOn()
      contourFilter.ComputeScalarsOn()
      contourFilter.UseScalarTreeOn()
      contourFilter.SetValue(1, 10)
      # contourFilter.SetValue(2,13)
      # contourFilter.SetValue(3,15)
      # contourFilter.SetValue(4,20)
      # contourFilter.SetValue(5,25)
      contourFilter.Update()
      isoSurface = contourFilter.GetOutputDataObject(0)

      self.AddContour(isoSurface)

  def hideIsoSurfaces(self):
    """
    Hide radiation isosurfaces from models of the visible needles only
    """
    # research
    profprint()
    contourNode = slicer.util.getNode(self.contourNode)
    widget = slicer.modules.NeedleFinderWidget
    if contourNode != None:
      contourNode.SetDisplayVisibility(abs(widget.hideContourButton.isChecked() - 1))
      contourNode.GetModelDisplayNode().SetSliceIntersectionVisibility(abs(widget.hideContourButton.isChecked() - 1))

  def displayNeedleTube(self, ID):
    """
    from segmentation report, show/hide needle tube
    """
    # productive #onButton #report
    profprint()
    modelNode = slicer.util.getNode('vtkMRMLModelNode' + str(ID))
    displayNode = modelNode.GetModelDisplayNode()
    nVisibility = displayNode.GetVisibility()
    # print nVisibility
    if nVisibility:
      displayNode.SliceIntersectionVisibilityOff()
      displayNode.SetVisibility(0)
      # also turn off yellow slice
      sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
      if sYellow == None :
        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
      sYellow.SetSliceVisible(0)
      reformatLogic = slicer.vtkSlicerReformatLogic()
      reformatLogic.SetSliceNormal(sYellow, 1, 0, 0)
      sYellow.Modified()
    else:
      displayNode.SliceIntersectionVisibilityOn()
      displayNode.SetVisibility(1)

  def reformatSagittalView4Needle(self, ID):
    """
    reformat sagittal view to be tangent to needle and display a 3D plane
    """
    # productive #onButton #report
    profprint()
    for i in range(2):  # workaround update problem
      modelNode = slicer.util.getNode('vtkMRMLModelNode' + str(ID))
      polyData = modelNode.GetPolyData()
      nb = polyData.GetNumberOfPoints()
      base = [0, 0, 0]
      tip = [0, 0, 0]
      polyData.GetPoint(nb - 1, tip)
      polyData.GetPoint(0, base)
      a, b, c = tip[0] - base[0], tip[1] - base[1], tip[2] - base[2]
      # print a,b,c
      sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
      if sYellow == None :
        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
      reformatLogic = slicer.vtkSlicerReformatLogic()
      sYellow.SetSliceVisible(1)
      reformatLogic.SetSliceNormal(sYellow, 1, -a / b, 0)
      m = sYellow.GetSliceToRAS()
      m.SetElement(0, 3, base[0])
      m.SetElement(1, 3, base[1])
      m.SetElement(2, 3, base[2])
      sYellow.Modified()
               
  def findLabelNeedleID(self, ID):
    print "findLabelNeedleID"
    msgbox(whoami())
    """
    Takes the needle (vtkMRMLModelNode) with the right ID
    Evaluates the z-position of every 20 points of the vtkPolyData
    Takes the closest one to the surface of the template holes
    Find the closest hole to the needle and assign the label to the needle 
    """
    # research
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    imageData = volumeNode.GetImageData()
    imageDimensions = imageData.GetDimensions()
    m = vtk.vtkMatrix4x4()
    minZ = None
    mindist = None
    volumeNode.GetIJKToRASMatrix(m)
    Z = m.GetElement(2, 3)
    needleNode = slicer.mrmlScene.GetNodeByID(ID)
    polydata = needleNode.GetPolyData()
    nb = polydata.GetNumberOfPoints()
    for i in range(nb):
      if 20 * i < nb:
        pt = [0, 0, 0]
        polydata.GetPoint(20 * i, pt)
        if (pt[2] - Z) ** 2 < minZ or minZ == None:
          minZ = (pt[2] - Z) ** 2
          bestNB = 20 * i
    hole = self.setNeedleCoordinates()
    # print bestNB
    A = [0, 0, 0]
    polydata.GetPoint(bestNB, A)
    for j in xrange(63):
      delta = ((hole[0][j] - (A[0])) ** 2 + (hole[1][j] - A[1]) ** 2) ** (0.5)
      if delta < mindist or mindist == None:
        bestmatch = j
        mindist = delta
        
    result = [bestmatch, mindist]
    return result

  def computerPolydataAndMatrix(self):
    """
    ??? Used?
    """ 
    print "computerPolydataAndMatrix"
    msgbox(whoami())
    Cylinder = vtk.vtkCylinderSource()

    Cylinder.SetResolution(1000)
    Cylinder.SetCapping(1) 
    Cylinder.SetHeight(float(200.0))
    Cylinder.SetRadius(float(1.0))
    self.m_polyCylinder = Cylinder.GetOutput()
    
    quad = vtk.vtkQuadric()
    quad.SetCoefficients(1, 1, 1, 0, 0, 0, 0, 1, 0, 0)
    sample = vtk.vtkSampleFunction()
    sample.SetModelBounds(-30, 30, -60, 60, -30, 30)
    sample.SetCapping(0)
    sample.SetComputeNormals(1)
    sample.SetSampleDimensions(50, 50, 50)
    sample.SetImplicitFunction(quad)
    contour = vtk.vtkContourFilter()
    contour.SetInputConnection(sample.GetOutputPort())
    contour.ComputeNormalsOn()
    contour.ComputeScalarsOn()
    contour.GenerateValues(4, 0, 100)
    self.m_polyRadiation = contour.GetOutput()

    self.m_vtkmat = vtk.vtkMatrix4x4()
    self.m_vtkmat.Identity()

    RestruMatrix = vtk.vtkMatrix4x4()
    WorldMatrix = vtk.vtkMatrix4x4()
    Restru2WorldMatrix = vtk.vtkMatrix4x4()

    RestruMatrix.SetElement(0, 0, 0)
    RestruMatrix.SetElement(1, 0, 0)
    RestruMatrix.SetElement(2, 0, 0)
    RestruMatrix.SetElement(3, 0, 1)

    RestruMatrix.SetElement(0, 1, 1)
    RestruMatrix.SetElement(1, 1, 0)
    RestruMatrix.SetElement(2, 1, 0)
    RestruMatrix.SetElement(3, 1, 1)

    RestruMatrix.SetElement(0, 2, 0)
    RestruMatrix.SetElement(1, 2, 1)
    RestruMatrix.SetElement(2, 2, 0)
    RestruMatrix.SetElement(3, 2, 1)

    RestruMatrix.SetElement(0, 3, 0)
    RestruMatrix.SetElement(1, 3, 0)
    RestruMatrix.SetElement(2, 3, 1)
    RestruMatrix.SetElement(3, 3, 1)

    WorldMatrix.SetElement(0, 0, 0)
    WorldMatrix.SetElement(1, 0, 0)
    WorldMatrix.SetElement(2, 0, 0)
    WorldMatrix.SetElement(3, 0, 1)

    WorldMatrix.SetElement(0, 1, 1)
    WorldMatrix.SetElement(1, 1, 0)
    WorldMatrix.SetElement(2, 1, 0)
    WorldMatrix.SetElement(3, 1, 1)

    WorldMatrix.SetElement(0, 2, 0)
    WorldMatrix.SetElement(1, 2, 0)
    WorldMatrix.SetElement(2, 2, -1)
    WorldMatrix.SetElement(3, 2, 1)

    WorldMatrix.SetElement(0, 3, 0)
    WorldMatrix.SetElement(1, 3, 1)
    WorldMatrix.SetElement(2, 3, 0)
    WorldMatrix.SetElement(3, 3, 1)

    WorldMatrix.Invert()
    Restru2WorldMatrix.Multiply4x4(RestruMatrix, WorldMatrix, self.m_vtkmat)
  
  def AddContour(self, polyData):
    """
    Add caculated isosurfaces (self.drawIsoSurfaces) around visible needles to the scene
    and add opacity, color...
    Used by drawIsoSurface,0
    """
    # research
    # called by drawIsoSurfaces
    profprint()
    # print polyData
    scene = slicer.mrmlScene
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    # ??? i suppose here is a bug:
    print 'modelNodes: ', modelNodes
    print 'self.ContourNode: ', self.contourNode
    #!!! self.contourNode is None
    
    # bugfix>>>>
    modelNode = slicer.vtkMRMLModelNode()
    self.contourNode = modelNode.GetID()
    # print 'self.ContourNode: ', self.contourNode
    # <<<bugfix
    
    # contourNode = slicer.util.getNode(self.contourNode)
    # print 'contourNode: ',contourNode
    if self.contourNode != None:
      slicer.mrmlScene.RemoveNode(self.contourNode.GetStorageNode())
      self.contourNode.RemoveAllDisplayNodeIDs()
      slicer.mrmlScene.RemoveNode(self.contourNode)
      
    # modelNode = slicer.vtkMRMLModelNode()
    modelNode.SetScene(scene)
    modelNode.SetAndObservePolyData(polyData)
    # display node
    displayNode = slicer.vtkMRMLModelDisplayNode()
 
    modelNode.SetName('Contours')
    
    scene.AddNode(displayNode)
    scene.AddNode(modelNode)
     
    displayNode.SetVisibility(1)
    displayNode.SetOpacity(0.06)
    displayNode.SetSliceIntersectionVisibility(1)
    displayNode.SetScalarVisibility(1)
    displayNode.SetActiveScalarName('ImageScalars') 
    displayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileHotToColdRainbow2.txt')
    displayNode.SetScalarRange(10, 40)
    displayNode.SetBackfaceCulling(0)
    displayNode.SetScene(scene)
    scene.AddNode(displayNode)
    modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
    # add to scene
    displayNode.SetInputPolyData(modelNode.GetPolyData())
    scene.AddNode(modelNode)

    # self.contourNode = modelNode.GetID()

    qt.QApplication.processEvents()

  #----------------------------------------------------------------------------------------------
  """ Needle Detection"""
  #----------------------------------------------------------------------------------------------

  def array2(self):
    """
    Used if needle tips input is given trough a labelmap.
    Extract the coordinates of each labels (after IslandEffect)
    """
    profbox(whoami())
    # research
    inputLabelID = self.__needleLabelSelector.currentNode().GetID()
    labelnode = slicer.mrmlScene.GetNodeByID(inputLabelID)
    i = labelnode.GetImageData()
    shape = list(i.GetDimensions())
    shape.reverse()
    a = vtk.util.numpy_support.vtk_to_numpy(i.GetPointData().GetScalars()).reshape(shape)
    labels = []
    val = [[0, 0, 0] for i in range(a.max() + 1)]
    for i in xrange(2, a.max() + 1):
      w = numpy.transpose(numpy.where(a == i))
      # labels.append(w.mean(axis=0))
      val[i] = [0, 0, 0]
      val[i][0] = w[int(round(w.shape[0] / 2))][2]
      val[i][1] = w[int(round(w.shape[0] / 2))][1]
      val[i][2] = w[int(round(w.shape[0] / 2))][0]
      if val[i] not in self.previousValues:
        labels.append(val[i])
        self.previousValues.append(val[i])
    return labels

  def factorial(self, n):
    """
    factorial(n): return the factorial of the integer n.
    factorial(0) = 1
    factorial(n) with n<0 is -factorial(abs(n))
    """
    # productive #frequent #math
    if frequent: print profprint();
    result = 1
    for i in xrange(1, abs(n) + 1):
     result *= i
    if n >= 0:
      return result
    else:
      return -result
      
  def binomial(self, n, k):
    """
    calc's binomial coefficient
    """
    # productive #frequent #math
    if frequent: profprint();
    if not 0 <= k <= n:
      return 0
    if k == 0 or k == n:
      return 1
    # calculate n!/k! as one product, avoiding factors that 
    # just get canceled
    P = k + 1
    for i in xrange(k + 2, n + 1):
      P *= i
    # if you are paranoid:
    # C, rem = divmod(P, factorial(n-k))
    # assert rem == 0
    # return C
    return P // self.factorial(n - k)

  def Fibonacci(self, n):
    """
    calc's Fibonacci #
    """
    # productive #frequent #math
    if frequent: profprint();
    F = [0, 1]
    for i in range(1, n + 1):
      F.append(F[i - 1] + F[i])
    return F

  def stepSize(self, k, l):
    """
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle 
    """
    # productive
    F = self.Fibonacci(l)
    s = F[k + 1] / float(sum(self.Fibonacci(l)))
    return s

  def stepSizeAndre(self, k, l):
    """
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle 
    """
    # productive
    F = self.Fibonacci(l)
    s = F[k + 1] / float(sum(self.Fibonacci(l)) - 1)
    return s
  
  def stepSize13(self, k, l):
    '''MICCAI13 version
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle 
    '''
    F = self.Fibonacci(l + 1)
    s = (sum(self.Fibonacci(k + 1), -1) + F[k + 1]) / float(sum(self.Fibonacci(l + 1), -1))
    return s
  
  def sortTable(self, table, cols):
    """ 
    sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list 
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    # productive
    profprint()
    for col in reversed(cols):
      table = sorted(table, key=operator.itemgetter(col))
    return table

  def sortTableReverse(self, table, cols):
    """ 
    sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list 
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    # productive
    profprint()
    for col in reversed(cols):
      table = sorted(table, key=operator.itemgetter(col), reverse=True)
    return table

  def ijk2ras(self, A):
    """
    Convert IJK coordinates to RAS coordinates. The transformation matrix is the one 
    of the active volume on the red slice
    """
    # productive #math #coordinate-space-conversion #frequent
    if frequent: profprint()
    m = vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
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

  def ras2ijk(self, A):
    """
    Convert RAS coordinates to IJK coordinates. The transformation matrix is the one 
    of the active volume on the red slice
    """
    # productive #math #coordinate-space-conversion #frequent
    if frequent: profprint()
    m = vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    m.Invert()
    imageData = volumeNode.GetImageData()
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
  
  def needleDetection(self):
    """
    This solution is optional but not used anymore in the workflow. 
    Use the label map of the needle tips
    Apply the island effect
    Extract the coordinates of the islands (self.array2)
    Start a detection for each island (self.needleDetectionThread)
    TODO: multi-processing
    """
    # research #obsolete
    profbox(whoami())
    # Apply Island Effect
    editUtil = EditorLib.EditUtil.EditUtil()
    parameterNode = editUtil.getParameterNode()
    sliceLogic = editUtil.getSliceLogic()
    lm = slicer.app.layoutManager()
    sliceWidget = lm.sliceWidget('Red')
    islandsEffect = EditorLib.IdentifyIslandsEffectOptions()
    islandsEffect.setMRMLDefaults()
    islandsEffect.__del__()
    islandTool = EditorLib.IdentifyIslandsEffectLogic(sliceLogic)
    parameterNode.SetParameter("IslandEffect,minimumSize", '0')
    islandTool.removeIslands()
    # select the image node from the Red slice viewer
    m = vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    spacing = volumeNode.GetSpacing()
    # chrono starts
    self.t0 = time.clock()
    # get the coordinates from the label map
    label = self.array2()
    for I in xrange(len(label)):
      A = label[I]
      colorVar = I  # ??? /(len(label))
      self.needleDetectionThread(A, imageData, colorVar, spacing)
      if slicer.modules.NeedleFinderWidget.autoStopTip.isChecked():
        self.needleDetectionUPThread(A, imageData, colorVar, spacing)

  def placeNeedleShaftEvalMarker(self, A, imageData, colorVar, spacing):
    """
    Add a fiducial point to the vtkMRMLScence, where the mouse click was triggered. The fiducial points reprents a control
    point for a manually segmented needle (validation needle)

    :param A: RAS coordinates of the mouse click
    :param imageData: volumeNode.GetImageDate()
    :param colorVar: color of the fiducial point
    :param spacing: volumeNode.GetSpacing()
    :return: tableValueCtrPt : table containing control points of every validation needle
    """
    # productive #onClick
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    fiducial.SetName('.' + str(widget.validationNeedleNumber) + "-" + str(widget.stepNeedle)) 
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetFiducialCoordinates(self.ijk2ras(A))
    fiducial.SetAttribute('ValidationNeedle', '1')
    fiducial.SetAttribute('NeedleNumber', str(widget.validationNeedleNumber))
    fiducial.SetAttribute('NeedleStep', str(widget.stepNeedle))
    
    nth = int(widget.validationNeedleNumber)
    # print nth

    displayNode = fiducial.GetDisplayNode()
    displayNode.SetGlyphScale(2)
    displayNode.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
    textNode = fiducial.GetAnnotationTextDisplayNode()
    textNode.SetTextScale(4)
    textNode.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
    self.tableValueCtrPt[widget.validationNeedleNumber][widget.stepNeedle] = self.ijk2ras(A)

  def obturatorNeedle(self, A, imageData, colorVar, spacing):
    """ Use the mouse click coordinates to draw obturator needles:
    * For the first obturator needle, two points are necessary: give both extremities of an obturator needle
    * For the following needles, only give the tip of the needle. It will draw parallel to the first obturator needle
    and having the same length

    :param A: RAS coordinates of the mouse click
    :param imageData: volumeNode.GetImageDate()
    :param colorVar: color of the fiducial point
    :param spacing: volumeNode.GetSpacing()
    :return: obturator needle
    """
    # productive
    profprint()
    widget = slicer.modules.NeedleFinderWidget

    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetFiducialCoordinates(self.ijk2ras(A))
    fiducial.SetAttribute('ObturatorNeedle', '1')
    if self.obtuNeedle <= 1:
      needleNumber = 0
    else:
      needleNumber = self.obtuNeedle - 1
      needleStep = 0
    if self.obtuNeedle == 1:
      needleStep = 1
    elif self.obtuNeedle == 0:
      needleStep = 0

    fiducial.SetAttribute('NeedleNumber', str(needleNumber))
    fiducial.SetAttribute('NeedleStep', str(needleStep))
    fiducial.SetName('.obtu-' + str(needleNumber)) 
    
    nth = int(needleNumber)

    displayNode = fiducial.GetDisplayNode()
    displayNode.SetGlyphScale(2)
    displayNode.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
    textNode = fiducial.GetAnnotationTextDisplayNode()
    textNode.SetTextScale(4)
    textNode.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
    
    self.obtuNeedleValueCtrPt[needleNumber][needleStep] = self.ijk2ras(A)
    # print self.ijk2ras(A)
    # print "ctr pt: ",self.obtuNeedleValueCtrPt

    if needleNumber >= 1:
      Vx = self.obtuNeedleValueCtrPt[0][1][0] - self.obtuNeedleValueCtrPt[0][0][0]
      Vy = self.obtuNeedleValueCtrPt[0][1][1] - self.obtuNeedleValueCtrPt[0][0][1]
      Vz = self.obtuNeedleValueCtrPt[0][1][2] - self.obtuNeedleValueCtrPt[0][0][2]

      L = float(Vx ** 2 + Vy ** 2 + Vz ** 2) ** 0.5

      E = self.ijk2ras(A)
      Ex = E[0] + 100 * Vx / L
      Ey = E[1] + 100 * Vy / L
      Ez = E[2] + 100 * Vz / L
      self.obtuNeedleValueCtrPt[needleNumber][1] = [Ex, Ey, Ez]

    self.drawObturatorNeedles()
    widget.stop()
    widget.fiducialObturatorButton.checked = 1
    widget.start(3)

  def objectiveFunction(self, imageData, ijk, radiusNeedleParameter, spacing, gradientPonderation):
    """
    used by needleDetectionUPThread
    """
    # research #frequent
    if frequent: profprint()
    radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
    radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
    ijk[0] = int(round(ijk[0]))
    ijk[1] = int(round(ijk[1]))
    ijk[2] = int(round(ijk[2]))
    center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0] + 1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + 1, ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0] - 1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - 1, ijk[2], 0)

    if gradientPonderation != 0:
      g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
      g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
      g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
      g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
      g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
      g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
      g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
      g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)

      total = center / float(5) - ((g1 + g2 + g3 + g4 + g5 + g6 + g7 + g8) / float(8)) * gradientPonderation
    else:
      total = center / float(5)

    return total

  def objectiveFunctionLOG(self, imageData, ijk, radiusNeedleParameter, spacing, gradientPonderation):
    """
    ??? used?
    """
    # obsolete
    print "objectiveFunctionLOG"
    msgbox(whoami())
    """
    not used.
    idea was to test a different objective function
    """
    radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
    radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
    
    center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0] + 1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + 1, ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0] - 1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - 1, ijk[2], 0)

    if gradientPonderation != 0:
      g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
      g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
      g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
      g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
      g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
      g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
      g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
      g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)

      total = center / float(5) - ((g1 + g2 + g3 + g4 + g5 + g6 + g7 + g8) / float(8))
    else:
      total = center / float(5)

    return math.log(total / float(30) + 0.1)

    
  #------------------------------------------------------------------------------ 
  #
  #
  # # FIND THE OPTIMAL TIP IN A CIRCLE (center = mouse click)
  #
  #
  #------------------------------------------------------------------------------

  def findTip(self, A, imageData, radiusNeedle, coeff, sigmaValue, gradientPonderation, X, Y, Z):
    """
    Find tip
    """
    # productive #onClick
    profprint()
    radiusNeedle = int(radiusNeedle)
    A = [int(A[0]), int(A[1]), int(A[2])]
    print A
    minTotalTip = 0
    X = int(X)
    Y = int(Y)
    Z = int(Z)
    for I in range(-X, X):
      i = int(I / float(coeff))
      for J in range(-Y, Y):
        j = int(J / float(coeff))
        for k in range(1):
          v0 = 0
          totalTip = 0
          for l in range (-3, 1):
            v0 = 8 * imageData.GetScalarComponentAsDouble(A[0] + i, A[1] + j, A[2] + k + l, 0)
            
            v1 = imageData.GetScalarComponentAsDouble(A[0] + radiusNeedle + i, A[1] + j, A[2] + k + l, 0)
            v2 = imageData.GetScalarComponentAsDouble(A[0] - radiusNeedle + i, A[1] + j, A[2] + k + l, 0)
            v3 = imageData.GetScalarComponentAsDouble(A[0] + i, A[1] + radiusNeedle + j, A[2] + k + l, 0)
            v4 = imageData.GetScalarComponentAsDouble(A[0] + i, A[1] - radiusNeedle + j, A[2] + k + l, 0)
            
            totalTip += v0 - ((v1 + v2 + v3 + v4) / float(4)) * gradientPonderation
          
          rgauss = (i ** 2 
                            + j ** 2
                            + k ** 2) ** 0.5

          gaussianAttenuation = math.exp(-(rgauss / float(10)) ** 2 / float((2 * (sigmaValue / float(10)) ** 2)))
          totalTip = gaussianAttenuation * totalTip 
          
          # totalTip = v0
          if totalTip < minTotalTip or minTotalTip == 0:
            minTotalTip = totalTip
            IBest = A[0] + i
            JBest = A[1] + j
            KBest = A[2] + k
            P = [ 0 for n in range(5)]
            P[0] = [A[0] + i, A[1] + j, A[2] + k + l]
            P[1] = [A[0] + radiusNeedle + i, A[1] + j, A[2] + k + l]
            P[2] = [A[0] - radiusNeedle + i, A[1] + j, A[2] + k + l]
            P[3] = [A[0] + i, A[1] + radiusNeedle + j, A[2] + k + l]
            P[4] = [A[0] + i, A[1] - radiusNeedle + j, A[2] + k + l]
              
    """
    # Draw template
    for pi in range(5):
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetName(str(pi))
      fiducial.SetFiducialCoordinates(self.ijk2ras(P[pi]))
    """
    # print "bestTip:",IBest,JBest,KBest, minTotalTip
    # print "initialtip:", A
    AInit = A

    A = [IBest, JBest, KBest]

    return A
  
  #------------------------------------------------------------------------------ 
  #
  #
  # # TRACKING NEEDLE IN -Z DIRECTION
  #
  #
  #------------------------------------------------------------------------------

  def findAxialSegmentationLimitFromMarker(self):
    """
    Find the limit marker in the scene and return its z-coord.
    """
    # productive 
    profprint()
    asl = [0, 0, -float("inf")]
    coord = [0, 0, 0]
    try:
      nodes = slicer.util.getNodes('template slice position*')
      found = False
      for node in nodes.values():
        node.GetFiducialCoordinates(coord)
        aslNew = coord
        if aslNew[2] > asl[2]: 
          asl = aslNew
          if found:
            print "higher limit marker found in scene, z-limit [ras]: ", coord[2]
          else:
            print "first limit marker found in scene, z-limit [ras]: ", coord[2]
        if found:
          print "/!\ there should be only one axial limit marker!"
        found = True
    except:
      print "/!\ no z-limit marker in scene (required)!"
      msgbox("/!\ no z-limit marker in scene (required)!")
    if asl[2] == -float("inf"):
      asl = [0, 0, 0]
    return int(round(self.ras2ijk(asl)[2])), coord[2]
    
  def needleDetectionThread(self, A, imageData, colorVar, spacing, script=False):
    """
    Switches between the versions of the algorithm. For comparison tests.
    """
    # productive #onbutton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    widget.axialSegmentationLimit, widget.axialSegmentationLimitRAS = self.findAxialSegmentationLimitFromMarker()
    if widget.labelMapNode:
      labelData=widget.labelMapNode.GetImageData()
    else:
      labelData=None
    # select algo version
    if widget.algoVersParameter.value == 0:
      self.needleDetectionThreadCurrentDev(A, imageData, colorVar, spacing, script, labelData)
    elif widget.algoVersParameter.value == 1:
      self.needleDetectionThread13_1(A, imageData, colorVar, spacing, script, labelData)
    elif widget.algoVersParameter.value == 2:
      self.needleDetectionThread13_2(A, imageData, colorVar, spacing, script, labelData)
    elif widget.algoVersParameter.value == 3:
      self.needleDetectionThread13_3(A, imageData, labelData, widget.tempPointList, colorVar, spacing, bUp=False, bScript=script)

  def needleDetectionThreadCurrentDev(self, A, imageData, colorVar, spacing, script=False, imgLabelData=None):
    """
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    Is this a threaded function? No it is not yet unfortunately, but the idea was to do it!

    :param A: RAS coordinates of the needle tip
    :param imageData: volumeNode.GetImageData()
    :param colorVar: color of the needle
    :param spacing: volumneNode.GetSpacing()
    :return: a needle in 3D!!
    """
    # research
    profprint()
    global conesColor
    if conesColor: conesColor=(conesColor+1)%308; 
    if conesColor==0: conesColor=300
    # ## initialisation of the parameters
    ijk = [0, 0, 0]
    bestPoint = [0, 0, 0]
    mode = "circle"

    # ## load parameters from GUI

    widget = slicer.modules.NeedleFinderWidget

    distanceMax = widget.radiusMax.value
    gradientPonderation = widget.gradientPonderation.value
    sigmaValue = widget.sigmaValue.value
    # stepsize                    = widget.stepsize.value
    gaussianAttenuationChecked = widget.gaussianAttenuationButton.isChecked()
    gradient = widget.gradient.isChecked()
    numberOfPointsPerNeedle = max(1, widget.numberOfPointsPerNeedle.value - 1)
    nbRotatingIterations = widget.nbRotatingIterations.value
    radiusNeedleParameter = widget.radiusNeedleParameter.value
    axialSegmentationLimit = widget.axialSegmentationLimit
    lenghtNeedleParameter = widget.lenghtNeedleParameter.value / (spacing[2])
    autoCorrectTip = widget.autoCorrectTip.isChecked()
    exponent = widget.exponent.value
    drawFiducialPoints = widget.drawFiducialPoints.isChecked()
    autoStopTip = widget.autoStopTip.isChecked()

    # ## length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)
    A = [int(A[0]), int(A[1]), int(A[2])]
    if axialSegmentationLimit != None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    elif axialSegmentationLimit == None and widget.maxLength.isChecked():
      axialSegmentationLimit = 0
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    else:
      lenghtNeedle = lenghtNeedleParameter
    
    rMax = distanceMax / float(spacing[0])
    NbStepsNeedle = numberOfPointsPerNeedle - 1
    nbRotatingStep = nbRotatingIterations

    dims = [0, 0, 0]
    imageData.GetDimensions(dims)
    pixelValue = numpy.zeros(shape=(dims[0], dims[1], dims[2]))
    
    A0 = A
    # print A0
    
    self.controlPoints = []
    controlPointsIJK = []
    bestControlPoints = []

    radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
    radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
    
    #---------------------------------------------------------------------------------
    # look for the best tip in the neighboorhood of the mouse click
    coeff = 1  # to look every 0.2mm
    radiusSphere = 5
    X = coeff * radiusSphere / float(spacing[0])
    Y = coeff * radiusSphere / float(spacing[1])
    Z = 5 / float(spacing[2])
    # print "X,Y,Z",X,Y,Z
    #---------------------------------------------------------------------------------
    # find the tip in a circle
    if autoCorrectTip:
      A = self.findTip(A, imageData, radiusNeedle, coeff, sigmaValue, gradientPonderation, X, Y, Z)
    # keep the first control point as A0
    A0 = A
    #---------------------------------------------------------------------------------
    # Add points to the control point list    

    self.controlPoints.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))
    #---------------------------------------------------------------------------------
    # Draw fiducial points initial tip and found tip
    if drawFiducialPoints:
      oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      oFiducial.Initialize(slicer.mrmlScene)
      oFiducial.SetName('.c0_'+str(colorVar))
      oFiducial.SetFiducialCoordinates(self.ijk2ras(A))
      oFiducial.GetDisplayNode().SetColor(0,0,1)
      """
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetName('Best tip')
      fiducial.SetFiducialCoordinates(self.ijk2ras(A))
      
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetName('A init')
      fiducial.SetFiducialCoordinates(self.ijk2ras(AInit))
      """
    
    for step in range(0, NbStepsNeedle + 1):
      
      # step 0
      #------------------------------------------------------------------------------
      if step == 0:

        stepSize = self.stepSize(step, NbStepsNeedle) * lenghtNeedle

        Vx = 0
        Vy = 0
        Vz = -stepSize

        rMax = distanceMax / float(spacing[0])
        rIter = int(round(rMax))
        tIter = max(1, int(round(stepSize)))  # ## ??? stepSize can be smaller 1 and it is in mm not int index coordinates

        # print "stepsize 0:",stepSize
        
        tot = stepSize

      else:

        """
          step 1,2,...
          ------------------------------------------------------------------------------
                 [   vector V   ]
                 *--------------*---------------------X   -> direction of tracking
                tip0            A                    C0

                then, for the following step:
                                              tip0<-A, A<-C, C0 = A + K.V
        """
        """
        stepSize = self.stepSize(step+1,NbStepsNeedle+1)*lenghtNeedle
        #print '\nstepsize',step, ':',stepSize
        

        C0      = [ 2*A[0]-tip0[0],
                    2*A[1]-tip0[1],
                    A[2]-stepSize   ]
        """


        stepSize = self.stepSize(step + 1, NbStepsNeedle + 1) * lenghtNeedle
        rMax = max(stepSize, distanceMax / float(spacing[0])) # ??? why is stepSize not divided by spacing[0]
        rIter = max(15, min(20, int(rMax / float(spacing[0])))) # ??? why divide rMax again by spacing[0]
        tIter = max(1, int(round(stepSize)))  # ## ??? stepSize can be smaller 1 and it is in mm not int index coordinates
      
        # Vector V    
        Vx = A[0] - tip0[0]
        Vy = A[1] - tip0[1]
        Vz = A[2] - tip0[2]

      coeffSize = abs(stepSize) / spacing[2]
      if Vz != 0 :
        K = coeffSize / float(abs(Vz))
      else:
        break

      P0 = A
      C0 = [ P0[0] + K * Vx,
                    P0[1] + K * Vy,
                    P0[2] + K * Vz ]
      
      if drawFiducialPoints and 1: # show cone base markers b
        oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        oFiducial.Initialize(slicer.mrmlScene)
        oFiducial.SetName('.b'+str(step+1)+'_'+str(colorVar))
        oFiducial.SetFiducialCoordinates(self.ijk2ras(C0))
        oFiducial.GetDisplayNode().SetColor(0,0,1)
  
      estimator = 0
      minEstimator = 0  

      # radius variation
      for R in range(rIter + 1):

        r = R * (rMax / float(rIter))
        
        # ## angle variation from 0 to 360
        for thetaStep in xrange(nbRotatingStep):
          
          angleInDegree = (thetaStep * 360) / float(nbRotatingStep)
          theta = math.radians(angleInDegree)

          C = [ C0[0] + r * (math.cos(theta)),
                            C0[1] + r * (math.sin(theta)),
                            C0[2]]

          total = 0
          M = [[0, 0, 0] for i in xrange(int(tIter) + 1)]
          
         
          # calculates tIter = number of points per segment 
          # print tIter
          for t in xrange(tIter + 1):

            tt = t / float(tIter)
            
            # x,y,z coordinates
            for i in range(3):
              
              M[t][i] = (1 - tt) * A[i] + tt * C[i]
              ijk[i] = int(round(M[t][i]))
              
            # first, test if points are in the image space 
            if ijk[0] < dims[0] and ijk[0] > 0 and  ijk[1] < dims[1] and ijk[1] > 0 and ijk[2] < dims[2] and ijk[2] > 0:
              
              center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] + 1, ijk[1], ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] - 1, ijk[1], ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + 1, ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - 1, ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] + 1, ijk[1] + 1, ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] + 1, ijk[1] - 1, ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] - 1, ijk[1] + 1, ijk[2], 0)
              center += imageData.GetScalarComponentAsDouble(ijk[0] - 1, ijk[1] - 1, ijk[2], 0)

              total += center ** exponent
              if gradient == 1 and mode == "circle" :
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
                g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
                g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
                g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                
                # total += (center - ((g1+g2+g3+g4+g5+g6+g7+g8)/float(8))*gradientPonderation)/float(tIter)
                total += ((center - g1) ** gradientPonderation) / float(tIter)
                total += ((center - g2) ** gradientPonderation) / float(tIter)
                total += ((center - g3) ** gradientPonderation) / float(tIter)
                total += ((center - g4) ** gradientPonderation) / float(tIter)
                total += ((center - g5) ** gradientPonderation) / float(tIter)
                total += ((center - g6) ** gradientPonderation) / float(tIter)
                total += ((center - g7) ** gradientPonderation) / float(tIter)
                total += ((center - g8) ** gradientPonderation) / float(tIter)
               
                # total = self.objectiveFunctionLOG(imageData, ijk, radiusNeedleParameter, spacing, 1)

              if gradient == 1 and mode == "square" :
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
                
                total += (8 * center - ((g1 + g2 + g3 + g4) / float(4)) * gradientPonderation) / float(tIter)
               
                # total = self.objectiveFunctionLOG(imageData, ijk, radiusNeedleParameter, spacing, 1)
              # >>>>>>>>>>>>>>>>>>>>>> exp.02
              if imgLabelData: 
                fLabel = imgLabelData.GetScalarComponentAsFloat(ijk[0], ijk[1], ijk[2], 0) 
                if fLabel and fLabel < 300:
                  #print "# force high influence of found label: ",fLabel
                  fTotal -= 10000
                if conesColor: imgLabelData.SetScalarComponentFromFloat(ijk[0], ijk[1], ijk[2], 0, conesColor) #mark the search cones in fLabel volume
              # <<<<<<<<<<<<<<<<<<<<
          if R == 0:
            
            initialIntensity = total
            estimator = total
            
          if gaussianAttenuationChecked == 1 and step >= 2 :
            if step == NbStepsNeedle:
                sigmaValue = 100
            
            if Vz != 0:
              """ 
              stepSize    =(A[2] - C0[2])
              K           =stepSize/float(tip0[2]-A[2])

              X           = [ A[0] + K * (A[0]-tip0[0]),
                              A[1] + K * (A[1]-tip0[1]),
                              A[2] + K * (A[2]-tip0[2]) ]
              """

              rgauss = ((C[0] - C0[0]) ** 2 
                              + (C[1] - C0[1]) ** 2
                              + (C[2] - C0[2]) ** 2) ** 0.5

              gaussianAttenuation = math.exp(-(rgauss / float(rMax)) ** 2 / float((2 * (sigmaValue / float(10)) ** 2)))  # 1 for x=0, 0.2 for x=5
              estimator = (total) * gaussianAttenuation # ??? this doesn't work as intended for negative values (they get larger!)
            else:
              estimator = total


          else:
            estimator = (total)
       
          if estimator < initialIntensity:

            if estimator < minEstimator or minEstimator == 0:
              minEstimator = estimator
              if minEstimator != 0:  
                bestPoint = C
        
           
      tip0 = A
      if bestPoint == [0, 0, 0]:
        A = C0
      elif bestPoint != tip0: 
        A = bestPoint

      # save the value of the objective function for the initial step.
      # will be used as reference for the initial step of the ascending tracking
      if step == 1:
        self.estimatorReference = minEstimator  
 

      if A[2] < axialSegmentationLimit and A != A0:
        
        asl = axialSegmentationLimit
        l = (A[2] - asl) / float(tip0[2] - A[2])

        A = [  A[0] - l * (tip0[0] - A[0]),
                A[1] - l * (tip0[1] - A[1]),
                A[2] - l * (tip0[2] - A[2])]

      self.controlPoints.append(self.ijk2ras(A))
      controlPointsIJK.append(A)
      # print('step:',step,':',minEstimator )
      if drawFiducialPoints:
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.c' +str(step)+'_'+ str(colorVar))
        fiducial.SetFiducialCoordinates(self.controlPoints[step + 1])

      if A[2] <= axialSegmentationLimit and A != A0:
        break
    
    if not autoStopTip:
      self.addNeedleToScene(self.controlPoints, colorVar, 'Detection', script)
  
  def needleDetectionThread13_1(self, A, imageData, colorVar, spacing, script=False, imgLabelData=None):
    '''MICCAI2013 suspect version, 3/11/13
    iGyne_old b16872c19a3bc6be1f4a9722e5daf16a603393f6
    https://github.com/gpernelle/iGyne_old/commit/b16872c19a3bc6be1f4a9722e5daf16a603393f6#diff-8ab0fe8b431d2af8b1aff51977e85ca2
    
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    # productive #probablyMiccai
    profprint()
    global conesColor
    if conesColor: conesColor=(conesColor+1)%308; 
    if conesColor==0: conesColor=300
    # ## initialisation of the parameters
    ijk = [0, 0, 0]
    bestPoint = [0, 0, 0]
    widget = slicer.modules.NeedleFinderWidget

    # ## load parameters from GUI
    distanceMax = widget.radiusMax.value
    gradientPonderation = widget.gradientPonderation.value
    sigmaValue = widget.sigmaValue.value
    stepsize = widget.stepsize.value
    gaussianAttenuationChecked = widget.gaussianAttenuationButton.isChecked()
    gradient = widget.gradient.isChecked()
    numberOfPointsPerNeedle = widget.numberOfPointsPerNeedle.value
    nbRotatingIterations = widget.nbRotatingIterations.value
    radiusNeedleParameter = widget.radiusNeedleParameter.value
    axialSegmentationLimit = widget.axialSegmentationLimit
    autoStopTip = widget.autoStopTip.isChecked()

    # ## length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)

    if axialSegmentationLimit != None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    else:
      lenghtNeedle = A[2] * 0.9 * spacing[2]
    
    rMax = distanceMax / float(spacing[0])
    NbStepsNeedle = numberOfPointsPerNeedle - 1
    nbRotatingStep = nbRotatingIterations

    dims = [0, 0, 0]
    imageData.GetDimensions(dims)
    pixelValue = numpy.zeros(shape=(dims[0], dims[1], dims[2]))
    
    A0 = A
    print A0
    if widget.drawFiducialPoints.isChecked():
      oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      oFiducial.Initialize(slicer.mrmlScene)
      oFiducial.SetName('.c0_'+str(colorVar))
      oFiducial.SetFiducialCoordinates(self.ijk2ras(A))
      oFiducial.GetDisplayNode().SetColor(0,0,1)
    
    controlPoints = []
    controlPointsIJK = []
    bestControlPoints = []
          
    controlPoints.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))

    for step in range(0, NbStepsNeedle + 2):
      print "length", lenghtNeedle
      # step 0
      #------------------------------------------------------------------------------
      if step == 0:

        L = self.stepSize13(step + 1, NbStepsNeedle + 1) * lenghtNeedle
        C0 = [A[0], A[1], A[2] - L]
        rMax = distanceMax / float(spacing[0])
        rIter = rMax
        tIter = int(round(L))  # ??? L can be smaller 1 and it is in mm not int index coordinates

      # step 1,2,...
      #------------------------------------------------------------------------------
      else:

        stepSize = self.stepSize13(step + 1, NbStepsNeedle + 1) * lenghtNeedle
        print stepSize

        C0 = [ 2 * A[0] - tip0[0],
                    2 * A[1] - tip0[1],
                    A[2] - stepSize   ]  # ??? this is buggy vector calculus, now its a feature ;-)

        rMax = max(stepSize, distanceMax / float(spacing[0]))
        rIter = max(15, min(20, int(rMax / float(spacing[0])))) # ??? why divide again by spacing[0]
        tIter = stepSize  # ## ??? stepSize can be smaller 1 and it is in mm not int index coordinates
      
      if widget.drawFiducialPoints.isChecked() and 1: # show cone base markers b
        oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        oFiducial.Initialize(slicer.mrmlScene)
        oFiducial.SetName('.b'+str(step+1)+'_'+str(colorVar))
        oFiducial.SetFiducialCoordinates(self.ijk2ras(C0))
        oFiducial.GetDisplayNode().SetColor(0,0,1)
  
      estimator = 0
      minEstimator = 0  

      # radius variation
      for R in range(int(rIter) + 1):

        r = R * (rMax / float(rIter))
        
        # ## angle variation from 0 to 360
        for thetaStep in xrange(int(nbRotatingStep)):
          
          angleInDegree = (thetaStep * 360) / float(nbRotatingStep)
          theta = math.radians(angleInDegree)

          C = [ C0[0] + r * (math.cos(theta)),
                            C0[1] + r * (math.sin(theta)),
                            C0[2]]

          total = 0
          M = [[0, 0, 0] for i in xrange(int(tIter) + 1)]
          
         
          # calculates tIter = number of points per segment 
          for t in xrange(int(tIter) + 1):

            tt = t / float(tIter)
            
            # x,y,z coordinates
            for i in range(3):
              
              M[t][i] = (1 - tt) * A[i] + tt * C[i]
              ijk[i] = int(round(M[t][i]))
              
            # first, test if points are in the image space 
            if ijk[0] < dims[0] and ijk[0] > 0 and  ijk[1] < dims[1] and ijk[1] > 0 and ijk[2] < dims[2] and ijk[2] > 0:
              
              center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
              total += center
              if gradient == 1 :

                radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
                radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
                g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
                g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
                g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                
                total += 8 * center - ((g1 + g2 + g3 + g4 + g5 + g6 + g7 + g8) / 8) * gradientPonderation
              # >>>>>>>>>>>>>>>>>>>>>> exp.02
              if imgLabelData: 
                fLabel = imgLabelData.GetScalarComponentAsFloat(ijk[0], ijk[1], ijk[2], 0) 
                if fLabel and fLabel < 300:
                  #print "# force high influence of found label: ",fLabel
                  fTotal -= 10000
                if conesColor: imgLabelData.SetScalarComponentFromFloat(ijk[0], ijk[1], ijk[2], 0, conesColor) #mark the search cones in fLabel volume
              # <<<<<<<<<<<<<<<<<<<<
          if R == 0:
            
            initialIntensity = total
            estimator = total
            
          if gaussianAttenuationChecked == 1 and step >= 2 :
            
            if tip0[2] - A[2] != 0:
            
                stepSize = (A[2] - C0[2])
                K = stepSize / float(tip0[2] - A[2])

                X = [ A[0] + K * (A[0] - tip0[0]),
                                A[1] + K * (A[1] - tip0[1]),
                                A[2] + K * (A[2] - tip0[2]) ]

                rgauss = ((C[0] - X[0]) ** 2 
                                + (C[1] - X[1]) ** 2
                                + (C[2] - X[2]) ** 2) ** 0.5

                gaussianAttenuation = math.exp(-(rgauss / float(rMax)) ** 2 / float((2 * (sigmaValue / float(10)) ** 2)))  # 1 for x=0, 0.2 for x=5
                estimator = (total) * gaussianAttenuation # ??? this doesn't work as intended for negative values (they get larger!)
            else:
                estimator = total


          else:
            estimator = (total)
       
          if estimator < initialIntensity:

            if estimator < minEstimator or minEstimator == 0:
              minEstimator = estimator
              if minEstimator != 0:  
                bestPoint = C
        
           
      tip0 = A
      if bestPoint == [0, 0, 0]:
        A = C0
      elif bestPoint != tip0: 
        A = bestPoint
 

      if A[2] < axialSegmentationLimit and A != A0:
        
        asl = axialSegmentationLimit
        l = (A[2] - asl) / float(tip0[2] - A[2])

        A = [  A[0] - l * (tip0[0] - A[0]),
                A[1] - l * (tip0[1] - A[1]),
                A[2] - l * (tip0[2] - A[2])]

      controlPoints.append(self.ijk2ras(A))
      controlPointsIJK.append(A)

      if widget.drawFiducialPoints.isChecked():
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.c_'+str(colorVar))
        fiducial.SetFiducialCoordinates(controlPoints[step + 1])

      if A[2] <= axialSegmentationLimit and A != A0:
        break
    
    # self.addNeedleToScene(controlPoints,colorVar)  
    if not autoStopTip:
      self.addNeedleToScene(controlPoints, colorVar, 'Detection', script)
      
  def needleDetectionThread13_2(self, A, imageData, colorVar, spacing, script=False, imgLabelData=None):
    '''MICCAI2013 suspect version, 3/11/13
    iGyne_old b16872c19a3bc6be1f4a9722e5daf16a603393f6
    https://github.com/gpernelle/iGyne_old/commit/b16872c19a3bc6be1f4a9722e5daf16a603393f6#diff-8ab0fe8b431d2af8b1aff51977e85ca2
    
    >>> same as 13_1, with bugfixes (e.g. concerning down stepSize or L "/spacing[2]") <<<
    
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    #productive #probablyMiccai #smallChanges
    profprint()
    global conesColor
    if conesColor: conesColor=(conesColor+1)%308; 
    if conesColor==0: conesColor=300
    # ## initialisation of the parameters
    ijk = [0, 0, 0]
    bestPoint = [0, 0, 0]
    widget = slicer.modules.NeedleFinderWidget

    # ## load parameters from GUI
    distanceMax = widget.radiusMax.value
    gradientPonderation = widget.gradientPonderation.value
    sigmaValue = widget.sigmaValue.value
    stepsize = widget.stepsize.value
    gaussianAttenuationChecked = widget.gaussianAttenuationButton.isChecked()
    gradient = widget.gradient.isChecked()
    numberOfPointsPerNeedle = widget.numberOfPointsPerNeedle.value
    nbRotatingIterations = widget.nbRotatingIterations.value
    radiusNeedleParameter = widget.radiusNeedleParameter.value
    axialSegmentationLimit = widget.axialSegmentationLimit
    autoStopTip = widget.autoStopTip.isChecked()

    # ## length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)

    if axialSegmentationLimit != None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    else:
      lenghtNeedle = A[2] * 0.9 * spacing[2]
    
    rMax = distanceMax / float(spacing[0])
    NbStepsNeedle = numberOfPointsPerNeedle - 1
    nbRotatingStep = nbRotatingIterations

    dims = [0, 0, 0]
    imageData.GetDimensions(dims)
    pixelValue = numpy.zeros(shape=(dims[0], dims[1], dims[2]))
    
    A0 = A
    print A0
    if widget.drawFiducialPoints.isChecked():
      oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      oFiducial.Initialize(slicer.mrmlScene)
      oFiducial.SetName('.c0_'+str(colorVar))
      oFiducial.SetFiducialCoordinates(self.ijk2ras(A))
      oFiducial.GetDisplayNode().SetColor(0,0,1)
    
    controlPoints = []
    controlPointsIJK = []
    bestControlPoints = []
          
    controlPoints.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))

    for step in range(0, NbStepsNeedle + 2):
      print "length", lenghtNeedle
      # step 0
      #------------------------------------------------------------------------------
      if step == 0:

        L = self.stepSize13(step + 1, NbStepsNeedle + 1) * lenghtNeedle
        #L=lenghtNeedle/NbStepsNeedle #<<< equal step size: better!
        C0 = [A[0], A[1], A[2] - L /spacing[2]] #<<< /spacing[2] bugfix
        rMax = distanceMax / float(spacing[0])
        rIter = rMax
        tIter = int(round(L))  ## /spacing[2] worse at beginnng! more steps??? L can be smaller 1 and it is in mm not int index coordinates

      # step 1,2,...
      #------------------------------------------------------------------------------
      else:

        stepSize = self.stepSize13(step + 1, NbStepsNeedle + 1) * lenghtNeedle
        #stepSize=lenghtNeedle/NbStepsNeedle #<<< equal step size: better!
        print stepSize

        C0 = [ 2 * A[0] - tip0[0],
                    2 * A[1] - tip0[1],
                    A[2] - stepSize /spacing[2]   ]  #<<< /spacing[2] bugfix # ??? this is buggy vector calculus, now its a feature ;-)
        #C0 = [A[0], A[1], A[2]+int(round(stepSize/spacing[2])) ] #<<< TODO test simply going down along z-axis
        rMax = max(stepSize, distanceMax / float(spacing[0]))
        rIter = max(15, min(20, int(rMax / float(spacing[0])))) # ??? why divide again by spacing[0]
        #tIter = stepSize      /spacing[2]  #more steps, slightly better! ??? stepSize can be smaller 1 and it is in mm not int index coordinates
      
      if widget.drawFiducialPoints.isChecked() and 1: # show cone base markers b
        oFiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        oFiducial.Initialize(slicer.mrmlScene)
        oFiducial.SetName('.b'+str(step+1)+'_'+str(colorVar))
        oFiducial.SetFiducialCoordinates(self.ijk2ras(C0))
        oFiducial.GetDisplayNode().SetColor(0,0,1)
  
      estimator = 0
      minEstimator = 0  

      # radius variation
      for R in range(int(rIter) + 1):

        r = R * (rMax / float(rIter))
        
        # ## angle variation from 0 to 360
        for thetaStep in xrange(int(nbRotatingStep)):
          
          angleInDegree = (thetaStep * 360) / float(nbRotatingStep)
          theta = math.radians(angleInDegree)

          C = [ C0[0] + r * (math.cos(theta)),
                            C0[1] + r * (math.sin(theta)),
                            C0[2]]

          total = 0
          M = [[0, 0, 0] for i in xrange(int(tIter) + 1)]
          
         
          # calculates tIter = number of points per segment 
          for t in xrange(int(tIter) + 1):

            tt = t / float(tIter)
            
            # x,y,z coordinates
            for i in range(3):
              
              M[t][i] = (1 - tt) * A[i] + tt * C[i]
              ijk[i] = int(round(M[t][i]))
              
            # first, test if points are in the image space 
            if ijk[0] < dims[0] and ijk[0] > 0 and  ijk[1] < dims[1] and ijk[1] > 0 and ijk[2] < dims[2] and ijk[2] > 0:
              
              center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
              total += center
              if gradient == 1 :

                radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
                radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
                g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
                g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
                g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                
                total += 8 * center - ((g1 + g2 + g3 + g4 + g5 + g6 + g7 + g8) / 8) * gradientPonderation
              # >>>>>>>>>>>>>>>>>>>>>> exp.02
              if imgLabelData: 
                fLabel = imgLabelData.GetScalarComponentAsFloat(ijk[0], ijk[1], ijk[2], 0) 
                if fLabel and fLabel < 300:
                  #print "# force high influence of found label: ",fLabel
                  fTotal -= 10000
                if conesColor: imgLabelData.SetScalarComponentFromFloat(ijk[0], ijk[1], ijk[2], 0, conesColor) #mark the search cones in fLabel volume
              # <<<<<<<<<<<<<<<<<<<<
          if R == 0:
            
            initialIntensity = total
            estimator = total
            
          if gaussianAttenuationChecked == 1 and step >= 2 :
            
            if tip0[2] - A[2] != 0:
            
                stepSize = (A[2] - C0[2])
                K = stepSize / float(tip0[2] - A[2])

                X = [ A[0] + K * (A[0] - tip0[0]),
                                A[1] + K * (A[1] - tip0[1]),
                                A[2] + K * (A[2] - tip0[2]) ]

                rgauss = ((C[0] - X[0]) ** 2 
                                + (C[1] - X[1]) ** 2
                                + (C[2] - X[2]) ** 2) ** 0.5

                gaussianAttenuation = math.exp(-(rgauss / float(rMax)) ** 2 / float((2 * (sigmaValue / float(10)) ** 2)))  # 1 for x=0, 0.2 for x=5
                estimator = (total) * gaussianAttenuation # ??? this might not work as intended for negative values (they get larger!)
                # >>> bugfix ? makes it even worse on average: bugfixbug ;-)
                #estimator=total
                #estimatorAtt = total * gaussianAttenuation 
                #estimator-=np.abs(estimator-estimatorAtt)
                # <<< xifgub
            else:
                estimator = total


          else:
            estimator = (total)
       
          if estimator < initialIntensity:

            if estimator < minEstimator or minEstimator == 0:
              minEstimator = estimator
              if minEstimator != 0:  
                bestPoint = C
        
           
      tip0 = A
      if bestPoint == [0, 0, 0]:
        A = C0
      elif bestPoint != tip0: 
        A = bestPoint
 

      if A[2] < axialSegmentationLimit and A != A0:
        
        asl = axialSegmentationLimit
        l = (A[2] - asl) / float(tip0[2] - A[2])

        A = [  A[0] - l * (tip0[0] - A[0]),
                A[1] - l * (tip0[1] - A[1]),
                A[2] - l * (tip0[2] - A[2])]

      controlPoints.append(self.ijk2ras(A))
      controlPointsIJK.append(A)

      if widget.drawFiducialPoints.isChecked():
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.c_'+str(colorVar))
        fiducial.SetFiducialCoordinates(controlPoints[step + 1])

      if A[2] <= axialSegmentationLimit and A != A0:
        break
    
    # self.addNeedleToScene(controlPoints,colorVar)  
    if not autoStopTip:
      self.addNeedleToScene(controlPoints, colorVar, 'Detection', script)
      
  def needleDetectionThread13_3(self, ijkA, imgData, imgLabelData, lrasTempPoints, iColorVar, fvSpacing, bUp=False, bScript=False):
    '''MICCAI2013 version, 3/11/13
    iGyne_old b16872c19a3bc6be1f4a9722e5daf16a603393f6
    https://github.com/gpernelle/iGyne_old/commit/b16872c19a3bc6be1f4a9722e5daf16a603393f6#diff-8ab0fe8b431d2af8b1aff51977e85ca2
    
    >>> Andre's bug fixes & experiments here: e.g. use additional user information to fix outliers.
    >>> /!\ This site is under heavy construction. /!\
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in lvControlPointsRAS), used later. 
    Then, this iStep is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (iRMax) and its normal is collinear to the previous computed segment. (cf. ijkB) 
    nStepsNeedle iterations give nStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these nStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    #research
    profprint()
    msgbox("/!\ Detour: Heavy construction site. /!\ "); return

      
  #------------------------------------------------------------------------------ 
  #
  #
  # # TRACKING NEEDLE IN +Z DIRECTION
  #
  #
  #------------------------------------------------------------------------------
  def needleDetectionUPThread(self, A, imageData, colorVar, spacing, script=False):
    """
    Call different versions of needle detection up thread.
    """
    # research
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    widget.axialSegmentationLimit, widget.axialSegmentationLimitRAS = self.findAxialSegmentationLimitFromMarker()
    # select algo version
    if widget.algoVersParameter.value == 0:
      self.needleDetectionUPThreadCurrentDev(A, imageData, colorVar, spacing, script)
    if widget.algoVersParameter.value == 1:
      msgbox ("/!\ needleDetectionUPThread N/A for algoVersion 1"); print "/!\ needleDetectionUPThread N/A for algoVersion 1" 
    if widget.algoVersParameter.value == 2:
      msgbox ("/!\ needleDetectionUPThread N/A for algoVersion 2"); print "/!\ needleDetectionUPThread N/A for algoVersion 2"
    if widget.algoVersParameter.value == 3:
      if widget.labelMapNode:
        self.needleDetectionThread13_3(A, imageData, widget.labelMapNode.GetImageData(), widget.tempPointList, colorVar, spacing, bUp=True, bScript=script)
      else:
        self.needleDetectionThread13_3(A, imageData, None, widget.tempPointList, colorVar, spacing, bUp=True, bScript=script)
      
  def needleDetectionUPThreadCurrentDev(self, A, imageData, colorVar, spacing, script=False):
    """
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    """
    # research
    profprint()
    widget = slicer.modules.NeedleFinderWidget

    # ## initialisation of the parameters
    ijk = [0, 0, 0]
    bestPoint = [0, 0, 0]

    # ## load parameters from GUI
    distanceMax = widget.radiusMax.value
    gradientPonderation = widget.gradientPonderation.value
    sigmaValue = widget.sigmaValue.value
    stepsize = widget.stepsize.value
    gaussianAttenuationChecked = widget.gaussianAttenuationButton.isChecked()
    lookNeighborhood = widget.gradient.isChecked()
    numberOfPointsPerNeedle = max(1, widget.numberOfPointsPerNeedle.value - 1)
    nbRotatingIterations = widget.nbRotatingIterations.value
    radiusNeedleParameter = widget.radiusNeedleParameter.value
    # radiusNeedleParameter       = 1
    axialSegmentationLimit = widget.axialSegmentationLimit
    lenghtNeedleParameter = widget.lenghtNeedleParameter.value / (spacing[2])

    # ## length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)

    if axialSegmentationLimit != None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    elif axialSegmentationLimit == None and widget.maxLength.isChecked():
      axialSegmentationLimit = 0
      lenghtNeedle = abs(A[2] - axialSegmentationLimit) * 1.15 * spacing[2]
    else:
      lenghtNeedle = lenghtNeedleParameter
    
    rMax = distanceMax / float(spacing[0])
    NbStepsNeedle = numberOfPointsPerNeedle - 1
    nbRotatingStep = nbRotatingIterations

    dims = [0, 0, 0]
    imageData.GetDimensions(dims)
    pixelValue = numpy.zeros(shape=(dims[0], dims[1], dims[2]))
    
    A0 = A
    # print A0
    
    controlPointsUP = []
    controlPointsIJK = []
    bestControlPoints = []
    minEstimator0 = None
    stopTracking = 0
    
    controlPointsUP.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))
    
    radiusNeedle = int(round(radiusNeedleParameter / float(spacing[0])))
    radiusNeedleCorner = int(round((radiusNeedleParameter / float(spacing[0]) / 1.414)))
    """
    #---------------------------------------------------------------------------------
    # look for the best tip in the neighboorhood of the mouse click
    X=10/float(spacing[0])
    Y=10/float(spacing[1])
    Z=10/float(spacing[2])
    #print "X,Y,Z",X,Y,Z
    minTotalTip=0
       
    for i in range(-3,3):
      for j in range(-3,3):
          for k in range(-3,3):
            for l in range (-3,1):
                v0 = 8 * imageData.GetScalarComponentAsDouble(ijk[0]+i, ijk[1]+j, ijk[2]+k+l, 0)
                v1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle+i, ijk[1]+j, ijk[2]+k+l, 0)
                v2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle+i, ijk[1]+j, ijk[2]+k+l, 0)
                v3 = imageData.GetScalarComponentAsDouble(ijk[0]+i, ijk[1]+radiusNeedle+j, ijk[2]+k+l, 0)
                v4 = imageData.GetScalarComponentAsDouble(ijk[0]+i, ijk[1]-radiusNeedle+j, ijk[2]+k+l, 0)
                v5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner+i, ijk[1]+radiusNeedleCorner+j, ijk[2]+k+l, 0)                    
                v6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner+i, ijk[1]-radiusNeedleCorner+j, ijk[2]+k+l, 0)
                v7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner+i, ijk[1]+radiusNeedleCorner+j, ijk[2]+k+l, 0)
                v8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner+i, ijk[1]-radiusNeedleCorner+j, ijk[2]+k+l, 0)
            totalTip = v0-(v1+v2+v3+v4+v5+v6+v7+v8/float(8))*gradientPonderation
            if totalTip<minTotalTip or minTotalTip==0:
              minTotalTip = totalTip
              IBest = ijk[0]+i
              JBest = ijk[1]+j
              KBest = ijk[2]+k

    
    #print "bestTip:",IBest,JBest,KBest, minTotalTip
    #print "initialtip:", A
    #---------------------------------------------------------------------------------
    """

    for step in range(0, NbStepsNeedle + 1):
      
      # step 0
      #------------------------------------------------------------------------------
      if step == 0:

        stepSize = self.stepSize(step, NbStepsNeedle) * lenghtNeedle

        Vx = 0
        Vy = 0
        Vz = stepSize

        C0 = [A[0], A[1], A[2] + stepSize]
        rMax = stepSize / float(spacing[0])
        rIter = int(round(rMax))
        tIter = max(1, int(round(stepSize)))  # ## ??? stepSize can be smaller 1 and it is in mm not int index coordinates

        # print "stepsize 0:",stepSize
        
        # tot     = stepSize

      # step 1,2,...
      #------------------------------------------------------------------------------
      else:

        stepSize = self.stepSize(step + 1, NbStepsNeedle + 1) * lenghtNeedle
      
        Vx = A[0] - tip0[0]
        Vy = A[1] - tip0[1]
        Vz = A[2] - tip0[2]

      coeffSize = abs(stepSize) / spacing[2]
      if Vz != 0 :
        K = coeffSize / float(abs(Vz))
      else:
        break

      P0 = A
      P1 = [ P0[0] + K * Vx,
                    P0[1] + K * Vy,
                    P0[2] + K * Vz ]

      # value of the objective function. We want to minimize it.
      dichoStep = 0
      continueDichotomy = 1

      # In order to find the tip, if the last point is beyond the tip (tested function of 
      # the relative value of the objective function), we start a dichotomy
      # the dichotomy runs until a) point below the tip  or b) more than 7 loops
      testSuccess = None
      while continueDichotomy == 1 and dichoStep <= 7 and stopTracking == 0 :
        # reset values
        estimator = 0
        minEstimator = 0
        dichoStep += 1
        if step != 100:
          
          if dichoStep > 1:

            K /= float(2)
            stepSize /= float(2)

            if testSuccess == 1:
              P0 = P1
            else:
              P0 = P0

            P1 = [ P0[0] + K * Vx,
                      P0[1] + K * Vy,
                      P0[2] + K * Vz ]
          # print "\t----------------------------------------"
          # print '\nstepsize',step, ':', stepSize
          # tot     += stepSize

          """
          C0      = [ 2*A[0]-tip0[0],
                      2*A[1]-tip0[1],
                      A[2]+stepSize   ]
          """

          """
          coeffSize   = abs(stepSize)
          K           = coeffSize/float(abs(Vz))

          
          C0           = [ A[0] + K * Vx,
                          A[1] + K * Vy,
                          A[2] + K * Vz ]
          """

          C0 = P1

          rMax = stepSize / float(spacing[0])
          rIter = max(15, min(20, int(rMax / float(spacing[0]))))
          tIter = max(3, int(round(stepSize)))
          # print "\trMax:",rMax, "rIter:",rIter, "tIter",tIter
          # print "\tP1:",P1[2]
      
        # radius variation
        for R in range(rIter + 1):

          r = R * (rMax / float(rIter))
          
          # ## angle variation from 0 to 360
          for thetaStep in xrange(nbRotatingStep):
            
            angleInDegree = (thetaStep * 360) / float(nbRotatingStep)
            theta = math.radians(angleInDegree)

            C = [ C0[0] + r * (math.cos(theta)),
                              C0[1] + r * (math.sin(theta)),
                              C0[2]]

            total = 0
            M = [[0, 0, 0] for i in xrange(int(tIter) + 1)]
            
            # calculates tIter = number of points per segment 
            for t in xrange(tIter + 1):

              tt = t / float(tIter)
              
              # x,y,z coordinates
              for i in range(3):
                
                M[t][i] = (1 - tt) * A[i] + tt * C[i]
                ijk[i] = int(round(M[t][i]))
                
              # first, test if points are in the image space 
              if ijk[0] < dims[0] and ijk[0] > 0 and  ijk[1] < dims[1] and ijk[1] > 0 and ijk[2] < dims[2] and ijk[2] > 0:
                
                center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
                total += center / float(tIter)
                if lookNeighborhood == 1 :

                  
                  
                  g1 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedle, ijk[1], ijk[2], 0)
                  g2 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedle, ijk[1], ijk[2], 0)
                  g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] + radiusNeedle, ijk[2], 0)
                  g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1] - radiusNeedle, ijk[2], 0)
                  g5 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)                    
                  g6 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                  g7 = imageData.GetScalarComponentAsDouble(ijk[0] - radiusNeedleCorner, ijk[1] + radiusNeedleCorner, ijk[2], 0)
                  g8 = imageData.GetScalarComponentAsDouble(ijk[0] + radiusNeedleCorner, ijk[1] - radiusNeedleCorner, ijk[2], 0)
                  
                  total += (8 * center - ((g1 + g2 + g3 + g4 + g5 + g6 + g7 + g8) / float(8)) * gradientPonderation) / float(tIter)
                
            if R == 0:
              
              initialIntensity = total
              estimator = total
              
            if gaussianAttenuationChecked == 1 and step >= 1 :
              
              if Vz != 0:

                  """
                  coeffSize    =abs((A[2] - C0[2]))
                  K           =coeffSize/float(abs(tip0[2]-A[2]))

                  X           = [ A[0] + K * (A[0]-tip0[0]),
                                  A[1] + K * (A[1]-tip0[1]),
                                  A[2] + K * (A[2]-tip0[2]) ]
                  """

                  rgauss = ((C[0] - C0[0]) ** 2 
                                  + (C[1] - C0[1]) ** 2
                                  + (C[2] - C0[2]) ** 2) ** 0.5

                  gaussianAttenuation = math.exp(-(rgauss / float(rMax)) ** 2 / float((2 * (sigmaValue / float(10)) ** 2)))  # 1 for x=0, 0.2 for x=5
                  estimator = (total) * gaussianAttenuation
              else:
                  estimator = total

            else:
              estimator = (total)
         
            if estimator < initialIntensity:

              if estimator < minEstimator or minEstimator == 0:
                minEstimator = estimator
                
                if minEstimator != 0:  
                  bestPoint = C
          
        # print "\tInitial Intensity:",initialIntensity
        # print "\tMin Estimator:",minEstimator
        
        if step == 0:
          minEstimator0 = self.estimatorReference

        if minEstimator0 != None and minEstimator0 != 0:
          RelMinEstimator = abs((minEstimator - minEstimator0) / float(minEstimator0))
          
          # print "\tmin Estimator 0 :",minEstimator0,"\n"
          # print "\tRel Estimator :",RelMinEstimator,"\n"
          valCtrPt = self.objectiveFunction(imageData, A, 3, spacing, 1)
          # print "\tObjective function Ctl Pt: ", valCtrPt

          if dichoStep >= 8:
            stopTracking = 1
            bestPoint = A
            break
          if ((RelMinEstimator < 0.6) and valCtrPt < 0 and minEstimator0 < 0) or (minEstimator < -80 and valCtrPt < 0):
            testSuccess = 1
            if dichoStep > 1:
              continueDichotomy = 0
              stopTracking = 1
              break
            elif dichoStep == 1:
              continueDichotomy = 0
          else:
            testSuccess = 0

      minEstimator0 = minEstimator
      tip0 = A
      if bestPoint == [0, 0, 0]:  # if the initial point (center of the cone) is indeed the optimal ctrl point
        A = C0
      elif bestPoint != tip0: 
        A = bestPoint
 
      controlPointsUP.append(self.ijk2ras(A))
      controlPointsIJK.append(A)

      if widget.drawFiducialPoints.isChecked():
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('..' + str(step) + '.' + str(self.objectiveFunction(imageData, A, 3, spacing, 1))+'_'+str(colorVar))
        fiducial.SetFiducialCoordinates(controlPointsUP[step + 1])
        fiducial.GetDisplayNode().SetColor(1, 1, 0)
        
      if A[2] <= axialSegmentationLimit and A != A0:
        break
    
    for i in range(len(controlPointsUP)):
      self.controlPoints.append(controlPointsUP[i])
    self.addNeedleToScene(self.controlPoints, colorVar, 'Detection', script)
    # print 'length:',tot

  def drawObturatorNeedles(self):
    """
    Draw needles around the obturator of length realNeedleLength
    Draw straigth lines, parallel to the one defined by two control points
    given by the first two clicks
    """
    # productive
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    realNeedleLength = widget.realNeedleLength.value

    # reset report table
    self.table = None
    self.row = 0
    self.initTableView()
    while slicer.util.getNodes('obturator-seg*') != {}:
      nodes = slicer.util.getNodes('obturator-seg*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    
    if self.obtuNeedleValueCtrPt == [[[]]]:
      self.obtuNeedleValueCtrPt = [[[999, 999, 999] for i in range(10)] for j in range(10)]
    if self.obtuNeedlePt == [[[]]]:
      self.obtuNeedlePt = [[[999, 999, 999] for i in range(10)] for j in range(10)]
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
    nbNode = modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
      modelNode = slicer.mrmlScene.GetNthNodeByClass(nthNode, 'vtkMRMLAnnotationFiducialNode')
      if modelNode.GetAttribute("ObturatorNeedle") == "1":
        needleNumber = int(modelNode.GetAttribute("NeedleNumber"))
        needleStep = int(modelNode.GetAttribute("NeedleStep"))
        coord = [0, 0, 0]
        modelNode.GetFiducialCoordinates(coord)
        if needleNumber == 0:
          self.obtuNeedleValueCtrPt[needleNumber][needleStep] = coord
        
    for i in range(0, len(self.obtuNeedleValueCtrPt)):

      sign = cmp(self.obtuNeedleValueCtrPt[0][0][2], self.obtuNeedleValueCtrPt[0][1][2])
      if (i == 0 and sign <= -1):
        AA = self.obtuNeedleValueCtrPt[0][0][2]
        BB = self.obtuNeedleValueCtrPt[0][1][2]
        self.obtuNeedleValueCtrPt[0][0][2] = BB
        self.obtuNeedleValueCtrPt[0][1][2] = AA

      # As we give the tip of the obturator needles, we only want to g in the increasing z direction.

      Vx = self.obtuNeedleValueCtrPt[0][1][0] - self.obtuNeedleValueCtrPt[0][0][0]
      Vy = self.obtuNeedleValueCtrPt[0][1][1] - self.obtuNeedleValueCtrPt[0][0][1]
      Vz = self.obtuNeedleValueCtrPt[0][1][2] - self.obtuNeedleValueCtrPt[0][0][2]

      L = float(Vx ** 2 + Vy ** 2 + Vz ** 2) ** 0.5

      E = self.obtuNeedleValueCtrPt[i][0]
      Ex = E[0] + realNeedleLength * Vx / L
      Ey = E[1] + realNeedleLength * Vy / L
      Ez = E[2] + realNeedleLength * Vz / L
      self.obtuNeedlePt[i][1] = [Ex, Ey, Ez]
      self.obtuNeedlePt[i][0] = [E[0], E[1], E[2]]
          # print needleNumber,needleStep,coord

    for i in range(len(self.obtuNeedlePt)):
      if self.obtuNeedlePt[i][0][0] != 999:
          colorVar = random.randrange(50, 100, 1)  # ## ??? /(100.)
          controlPointsUnsorted = [val for val in self.obtuNeedlePt[i] if val != [999, 999, 999]]
          controlPoints = controlPointsUnsorted
          # controlPoins = self.obtuNeedlePt[i]
          if ((i == 0 and len(controlPoints) >= 1) or i >= 1) :
            self.addNeedleToScene(controlPoints, i, 'Obturator')
      
  def drawValidationNeedles(self):
    """This function takes the values inside the table tableValueCtrPt and add attributes such as color, name ,.. for every
     validation needle.
     * To add the needle to the scene, the points given for every needle has to be sorted sagitally,so they can be used as
     control points in a Beziers curve
     * For each sets of needle points, the function addNeedleToScene fits a Bezier curve and render it as a
     tube (vtkMRMLModelNode)
    """ 
    # productive #onButton
    profprint()
    # reset report table
    # print "Draw manually segmented needles..."
    # self.table =None
    # self.row=0
    self.initTableView()
    self.deleteEvaluationNeedlesFromTable()
    while slicer.util.getNodes('manual-seg*') != {}:
        nodes = slicer.util.getNodes('manual-seg*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)
    
    if self.tableValueCtrPt == [[]]:
        self.tableValueCtrPt = [[[999, 999, 999] for i in range(100)] for j in range(100)]
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
    nbNode = modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
        modelNode = slicer.mrmlScene.GetNthNodeByClass(nthNode, 'vtkMRMLAnnotationFiducialNode')
        if modelNode.GetAttribute("ValidationNeedle") == "1":
          needleNumber = int(modelNode.GetAttribute("NeedleNumber"))
          needleStep = int(modelNode.GetAttribute("NeedleStep"))
          coord = [0, 0, 0]
          modelNode.GetFiducialCoordinates(coord)
          self.tableValueCtrPt[needleNumber][needleStep] = coord
          print needleNumber, needleStep, coord
          # print self.tableValueCtrPt[needleNumber][needleStep]

    for i in range(len(self.tableValueCtrPt)):
      if self.tableValueCtrPt[i][1] != [999, 999, 999]:
        colorVar = random.randrange(50, 100, 1)  # ??? /(100.)
        controlPointsUnsorted = [val for val in self.tableValueCtrPt[i] if val != [999, 999, 999]]
        controlPoints = self.sortTable(controlPointsUnsorted, (2, 1, 0))
        self.addNeedleToScene(controlPoints, i, 'Validation')
      else:
        # print i
        pass
        
  def addCSplineToScene(self, controlPoint, colorVar, needleType='Detection', endMarker=False, name="^", script=False):
    """Adds visual needle representation as interpolating cardinal spline to the scene. 
    Alternative to Bezier curves.

    :param controlPoint: array of RAS coordinates of points of a needle (used as control point for the Bezier's curve
    :param colorVar: color of the needle
    :param needleType: 'validation' for a manually segmentated needle, 'detection' for an automatically segmented needle,
    'obturator' for an obturator needle
    :return: visually, needle added to the scene
    """
    #research
    #profprint()
    """
    Create a model of the linear needle segments
    """
    widget = slicer.modules.NeedleFinderWidget

    realNeedleLength = widget.realNeedleLength.value
    extendNeedle = widget.extendNeedle.isChecked()
    
    # sort the points in a decreasing order (from tip to bottom)
    controlPointListSorted = controlPoint #self.sortTableReverse(controlPoint, (2, 1, 0))

    # calculate the length of the list of ctr points
    lenghtTotal = 0
    for i in range(len(controlPoint) - 1):
        lenghtTotal += self.distanceTwoPoints(controlPointListSorted[i + 1], controlPointListSorted[i])
    #print "Polygon added to scene, length of tube: ", lenghtTotal
    
    # in case we want to extend the needle to the wanted length
    """
    The extension is currently done by adding a point to the control point list.
    """
    if lenghtTotal < realNeedleLength and extendNeedle:
      lastPoint = [controlPointListSorted[-1][0], controlPointListSorted[-1][1], controlPointListSorted[-1][2] - (realNeedleLength - lenghtTotal)]
      controlPointListSorted.append(lastPoint)

    scene = slicer.mrmlScene
    # One spline for each direction.
    aSplineX = vtk.vtkCardinalSpline()
    aSplineY = vtk.vtkCardinalSpline()
    aSplineZ = vtk.vtkCardinalSpline()
    numberOfInputPoints = len(controlPointListSorted)
    inputPoints = vtk.vtkPoints()
    # start read out
    for i in range(numberOfInputPoints):      
      x,y,z = controlPointListSorted[i][0], controlPointListSorted[i][1], controlPointListSorted[i][2]
      aSplineX.AddPoint(i, x)
      aSplineY.AddPoint(i, y)
      aSplineZ.AddPoint(i, z)
      inputPoints.InsertPoint(i, x, y, z)
    # Generate the polyline for the spline.
    points = vtk.vtkPoints()
    profileData = vtk.vtkPolyData()
    # Number of points on the spline
    numberOfOutputPoints = 50
    # Interpolate x, y and z by using the three spline filters and
    # create new points
    for i in range(0, numberOfOutputPoints):
      t = (numberOfInputPoints-1.0)/(numberOfOutputPoints-1.0)*i
      points.InsertPoint(i, aSplineX.Evaluate(t), aSplineY.Evaluate(t), aSplineZ.Evaluate(t))
    # Create the polyline.
    lines = vtk.vtkCellArray()
    lines.InsertNextCell(numberOfOutputPoints)
    for i in range(0, numberOfOutputPoints): lines.InsertCellPoint(i)
    profileData.SetPoints(points)
    profileData.SetLines(lines)
    # Add thickness to the resulting line.
    profileTubes = vtk.vtkTubeFilter()
    profileTubes.SetNumberOfSides(8)
    profileTubes.SetInputData(profileData)
    profileTubes.SetRadius(1)
    profileTubes.SetNumberOfSides(50)
    profileTubes.Update()

    # ## Create model node
    model = slicer.vtkMRMLModelNode()
    model.SetScene(scene)
    model.SetAndObservePolyData(profileTubes.GetOutput())
    # ## Create display node
    modelDisplay = slicer.vtkMRMLModelDisplayNode()

    modelDisplay.SetScene(scene)
    scene.AddNode(modelDisplay)
    model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
    # ## Add to scene
    modelDisplay.SetInputPolyDataConnection(model.GetPolyDataConnection())
    scene.AddNode(model)
    model.GetDisplayNode().SliceIntersectionVisibilityOn()
    if needleType == 'Validation':
      model.SetName('.manual-seg_' + str(colorVar))
    elif needleType == 'Obturator':
      model.SetName('.obturator-seg_' + str(colorVar))
    else:
      model.SetName('.python-catch-round_' + str(self.round) + '-ID-' + str(model.GetID()))
    model.SetAttribute('type', needleType)
    
    if needleType == 'Validation':
      nth = int(colorVar) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth)) 
    
    else:
      nth = int(model.GetID().strip('vtkMRMLModelNode')) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth))
    
    if endMarker:
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.SetName('.'+name+'_'+str(colorVar))
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetFiducialCoordinates(controlPointListSorted[-1])
      fiducial.SetAttribute('TemporaryFiducial', '1')
      fiducial.SetLocked(True)
      displayNode = fiducial.GetDisplayNode()
      displayNode.SetGlyphScale(2.1)
      displayNode.SetColor(0, 0, 0)
      textNode = fiducial.GetAnnotationTextDisplayNode()
      textNode.SetTextScale(3)
      textNode.SetColor(0, 0, 0)
      
  def addPolyLineToScene(self, controlPoint, colorVar, needleType='Detection',script=False, endMarker=False, name="^", trans=0):
    """Just adds visual representation of linear (needle) segments to the scene. 
    Useful for drawing the control polygon of a smooth curve.

    :param controlPoint: array of RAS coordinates of points of a needle (used as control point for the Bezier's curve
    :param colorVar: color of the needle
    :param needleType: 'validation' for a manually segmentated needle, 'detection' for an automatically segmented needle,
    'obturator' for an obturator needle
    :return: visually, needle added to the scene
    """
    #research
    #profprint()
    """
    Create a model of the linear needle segments
    """
    widget = slicer.modules.NeedleFinderWidget

    realNeedleLength = widget.realNeedleLength.value
    extendNeedle = widget.extendNeedle.isChecked()
    
    # sort the points in a decreasing order (from tip to bottom)
    controlPointListSorted = controlPoint #self.sortTableReverse(controlPoint, (2, 1, 0))

    # calculate the length of the list of ctr points
    lenghtTotal = 0
    for i in range(len(controlPoint) - 1):
        lenghtTotal += self.distanceTwoPoints(controlPointListSorted[i + 1], controlPointListSorted[i])
    #print "Polygon added to scene, length of tube: ", lenghtTotal
    
    # in case we want to extend the needle to the wanted length
    """
    The extension is currently done by adding a point to the control point list.
    """
    if lenghtTotal < realNeedleLength and extendNeedle:
      lastPoint = [controlPointListSorted[-1][0], controlPointListSorted[-1][1], controlPointListSorted[-1][2] - (realNeedleLength - lenghtTotal)]
      controlPointListSorted.append(lastPoint)

    scene = slicer.mrmlScene
    points = vtk.vtkPoints()
    polyData = vtk.vtkPolyData()
    polyData.SetPoints(points)
    lines = vtk.vtkCellArray()
    polyData.SetLines(lines)
    linesIDArray = lines.GetData()
    linesIDArray.Reset()
    linesIDArray.InsertNextTuple1(0)
    polygons = vtk.vtkCellArray()
    polyData.SetPolys(polygons)
    idArray = polygons.GetData()
    idArray.Reset()
    idArray.InsertNextTuple1(0)
    n = len(controlPointListSorted)
    # start read out
    for i in range(n):      
      pointIndex = points.InsertNextPoint(*(controlPointListSorted[i]))
      linesIDArray.InsertNextTuple1(pointIndex)
      linesIDArray.SetTuple1(0, linesIDArray.GetNumberOfTuples() - 1)
      lines.SetNumberOfCells(1)
    # ## Create model node
    model = slicer.vtkMRMLModelNode()
    model.SetScene(scene)
    model.SetAndObservePolyData(polyData)
    # ## Create display node
    modelDisplay = slicer.vtkMRMLModelDisplayNode()

    modelDisplay.SetScene(scene)
    scene.AddNode(modelDisplay)
    model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
    # ## Add to scene
    modelDisplay.SetInputPolyDataConnection(model.GetPolyDataConnection())
    scene.AddNode(model)
    # ##Create Tube around the line
    tube = vtk.vtkTubeFilter()
    polyData = model.GetPolyData()
    tube.SetInputData(polyData)
    tube.SetRadius(1)
    tube.SetNumberOfSides(50)
    tube.Update()
    
    model.SetAndObservePolyData(tube.GetOutput())
    model.GetDisplayNode().SliceIntersectionVisibilityOn()
    model.GetDisplayNode().SetOpacity(1-trans)
    if needleType == 'Validation':
      model.SetName('.manual-seg_' + str(colorVar))
    elif needleType == 'Obturator':
      model.SetName('.obturator-seg_' + str(colorVar))
    else:
      model.SetName('.python-catch-round_' + str(self.round) + '-ID-' + str(model.GetID()))
    model.SetAttribute('type', needleType)
    
    if needleType == 'Validation':
      nth = int(colorVar) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth)) 
    
    else:
      nth = int(model.GetID().strip('vtkMRMLModelNode')) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth))
    
    if endMarker:
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.SetName('.'+name+'_'+str(colorVar))
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetFiducialCoordinates(controlPointListSorted[-1])
      fiducial.SetAttribute('TemporaryFiducial', '1')
      fiducial.SetLocked(True)
      displayNode = fiducial.GetDisplayNode()
      displayNode.SetGlyphScale(.5) # "arrow head"
      displayNode.SetColor(0, 0, 0)
      textNode = fiducial.GetAnnotationTextDisplayNode()
      textNode.SetTextScale(1)
      textNode.SetColor(0, 0, 0)

  def addNeedleToScene(self, controlPoint, colorVar, needleType='Detection', script=False):
    """Computes the Bezier's curve and adds visual representation of a needle to the scene

    :param controlPoint: array of RAS coordinates of points of a needle (used as control point for the Bezier's curve
    :param colorVar: color of the needle
    :param needleType: 'validation' for a manually segmentated needle, 'detection' for an automatically segmented needle,
    'obturator' for an obturator needle
    :return: visually, needle added to the scene
    """
    # productive
    profprint()
    """
    Create a model of the needle from its equation (Beziers curve fitting the control points)
    """
    widget = slicer.modules.NeedleFinderWidget

    realNeedleLength = widget.realNeedleLength.value
    extendNeedle = widget.extendNeedle.isChecked()
    
    # sort the points in a decreasing order (from tip to bottom)
    controlPointListSorted = self.sortTableReverse(controlPoint, (2, 1, 0))

    # calculate the length of the list of ctr points
    lenghtTotal = 0
    for i in range(len(controlPoint) - 1):
        lenghtTotal += self.distanceTwoPoints(controlPointListSorted[i + 1], controlPointListSorted[i])
    print "Needle added to scene, ",
    print 'lenght tube: ', lenghtTotal
    
    # in case we want to extend the needle to the wanted length
    """
    The extension is currently done by adding a point to the control point list.
    TODO: only append a straight tube, so it doesn't add a control point and modify
    the initial Bezier curve
    """
    if lenghtTotal < realNeedleLength and extendNeedle:
      lastPoint = [controlPointListSorted[-1][0], controlPointListSorted[-1][1], controlPointListSorted[-1][2] - (realNeedleLength - lenghtTotal)]
      controlPointListSorted.append(lastPoint)

    label = None
    scene = slicer.mrmlScene
    points = vtk.vtkPoints()
    polyData = vtk.vtkPolyData()
    polyData.SetPoints(points)
    lines = vtk.vtkCellArray()
    polyData.SetLines(lines)
    linesIDArray = lines.GetData()
    linesIDArray.Reset()
    linesIDArray.InsertNextTuple1(0)
    polygons = vtk.vtkCellArray()
    polyData.SetPolys(polygons)
    idArray = polygons.GetData()
    idArray.Reset()
    idArray.InsertNextTuple1(0)
    nbEvaluationPoints = 50
    n = len(controlPointListSorted) - 1
    Q = [[0, 0, 0] for t in range(nbEvaluationPoints + 1)]
    # start calculation
    for t in range(nbEvaluationPoints+1):  #<<< lil bug
      tt = float(t) / (1 * nbEvaluationPoints)
      for j in range(3):
        for i in range(n + 1):
          Q[t][j] += self.binomial(n, i) * (1 - tt) ** (n - i) * tt ** i * controlPointListSorted[i][j]
          
      pointIndex = points.InsertNextPoint(*Q[t])
      linesIDArray.InsertNextTuple1(pointIndex)
      linesIDArray.SetTuple1(0, linesIDArray.GetNumberOfTuples() - 1)
      lines.SetNumberOfCells(1)
    # ## Create model node
    model = slicer.vtkMRMLModelNode()
    model.SetScene(scene)
    model.SetAndObservePolyData(polyData)
    # ## Create display node
    modelDisplay = slicer.vtkMRMLModelDisplayNode()

    modelDisplay.SetScene(scene)
    scene.AddNode(modelDisplay)
    model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
    # ## Add to scene
    modelDisplay.SetInputPolyDataConnection(model.GetPolyDataConnection())
    scene.AddNode(model)
    # ##Create Tube around the line
    tube = vtk.vtkTubeFilter()
    polyData = model.GetPolyData()
    tube.SetInputData(polyData)
    tube.SetRadius(1)
    tube.SetNumberOfSides(50)
    tube.Update()
    
    model.SetAndObservePolyData(tube.GetOutput())
    model.GetDisplayNode().SliceIntersectionVisibilityOn()
    if needleType == 'Validation':
      model.SetName('manual-seg_' + str(colorVar))
    elif needleType == 'Obturator':
      model.SetName('obturator-seg_' + str(colorVar))
    else:
      model.SetName('python-catch-round_' + str(self.round) + '-ID-' + str(model.GetID()))
    model.SetAttribute('type', needleType)
    
    self.lastNeedleNames.append(model.GetName())
    
    # evaluate and print the processing time
    processingTime = time.clock() - self.t0
    # print processingTime
    
    if needleType == 'Validation':
      nth = int(colorVar) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth)) 
    
    else:
      nth = int(model.GetID().strip('vtkMRMLModelNode')) % 64
      modelDisplay.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
      model.SetAttribute("nth", str(nth))
    
    if needleType == 'Validation':
      1
      # self.addNeedleToTable(int(colorVar),label,'Validation') ### ??? why ID=color here
      # self.addNeedleToTable(int(model.GetID().strip('vtkMRMLModelNode')),label,'Validation')
    
    elif not script:
      self.addNeedleToTable(int(model.GetID().strip('vtkMRMLModelNode')), label)

  def deleteTempModels(self):
    """
    Delete control points from needle bezier curves.
    """
    # research
    # remove old control pts from scene
    while slicer.util.getNodes('.*') != {}:
      nodes = slicer.util.getNodes('.*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    # ruler measurements
    while slicer.util.getNodes('M*') != {}:
      nodes = slicer.util.getNodes('M*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
        
  def deleteAllAutoNeedlesFromScene(self):
    """
    Delete every segmented needle of the current set
    """
    # productive #onButton
    profprint()
    while slicer.util.getNodes('python-catch-round_' + str(self.round) + '*') != {}:
      nodes = slicer.util.getNodes('python-catch-round_' + str(self.round) + '*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
  
  def deleteAllModelsFromScene(self):
    """
    Delete every segmented needle, template slice markers and reset yellow segment
    """
    # research
    self.deleteNeedleDetectionModelsFromScene()
    self.deleteNeedleValidationModelsFromScene()
  
  def deleteNeedleValidationModelsFromScene(self):
    """
    Delete artifacts from validation from scene.
    """
    # producitve #onbutton
    profprint()
    while slicer.util.getNodes('manual-seg_*') != {}:
      nodes = slicer.util.getNodes('manual-seg_*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    while slicer.util.getNodes('obturator-seg_*') != {}:
      nodes = slicer.util.getNodes('obturator-seg_*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    # bezier control points
    self.deleteTempModels()
    while slicer.util.getNodes('template slice position*') != {}:
      nodes = slicer.util.getNodes('template slice position*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
      
  def deleteNeedleDetectionModelsFromScene(self):
    """
    Delete artifacts from semi-auto segmentation from scene.
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    # remove artifacts from segmentation editor, 3d models (from SE's model builder)
    if widget.currentLabel:
      for i in range(widget.currentLabel + 1):
        while slicer.util.getNodes(str(i)) != {}:
          nodes = slicer.util.getNodes(str(i))
          for node in nodes.values():
            slicer.mrmlScene.RemoveNode(node)
    # remove artifacts from needle finder
    while slicer.util.getNodes('python-catch-round_*') != {}:
      nodes = slicer.util.getNodes('python-catch-round_*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    # while slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode') !={}:
      # nodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
      # for node in nodes.values():
        # slicer.mrmlScene.RemoveNode(node)
    sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
    if sYellow == None :
        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
    sYellow.SetSliceVisible(0)
    reformatLogic = slicer.vtkSlicerReformatLogic()
    reformatLogic.SetSliceNormal(sYellow, 1, 0, 0)
    tempFidNodes = slicer.mrmlScene.GetNodesByName('Temp')
    for i in range(tempFidNodes.GetNumberOfItems()):
      node = tempFidNodes.GetItemAsObject(i)
      if node:
        slicer.mrmlScene.RemoveNode(node)
    # bezier control points
    self.deleteTempModels()
    sYellow.Modified()
        
  def deleteLastNeedle(self):
    """
    Delete last segmented needle of the current round
    """
    # productive #onButton
    profprint(self.getName())
    widget = slicer.modules.NeedleFinderWidget
    if widget.deleteNeedleButton.isEnabled() and self.lastNeedleNames:
      name = self.lastNeedleNames.pop()
      print "removing needle with name: ", name
      while slicer.util.getNodes(name + '*') != {}:
        nodes = slicer.util.getNodes(name + '*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)
      # rebuild report table
      ID = name.lstrip('python-catch-round_').lstrip('manual-seg_').lstrip('obturator-seg_').lstrip('0123456789').lstrip('-ID-vtkMRMLModelNode')
      print "needle ID: <%s>" % ID
      self.deleteNeedleFromTable(int(ID))

  def newInsertionNeedleSet(self):
    """
    Start a new round
    """
    # productive #onButton
    profbox()
    widget = slicer.modules.NeedleFinderWidget
    if widget.newInsertionButton:
      dialog = qt.QDialog()
      messageBox = qt.QMessageBox.information(dialog, 'Information', 'You are creating a new set of needles')
      self.round += 1
      widget.newInsertionButton.setText('Start a new set of needles - Round ' + str(self.round + 1) + '?')
      widget.deleteNeedleButton.setText('Delete Needles from round ' + str(self.round))

  def resetNeedleDetection(self, script=False):
    """
    Reset the needle detection to completely start over.
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    ret = 0
    if script == False:
        dialog = qt.QDialog()
        ret = messageBox = qt.QMessageBox.question(dialog, 'Attention', """
          Are you sure that you want to reset the needle detection?
          It will delete every segmented needles...
          """, qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    if ret == qt.QMessageBox.Ok or script == True:
      self.deleteNeedleDetectionModelsFromScene()
      self.previousValues = [[0, 0, 0]]
      self.round = 1
      if widget.newInsertionButton:
        widget.newInsertionButton.setText('Start a new set of needles (' + str(self.round + 1) + ') ?')
        widget.deleteNeedleButton.setText('Delete Needles from set (' + str(self.round) + ")")
      # reset report table
      self.table = None
      self.row = 0
      self.col = 0
      if not script:
        for i in self.items:
          item = self.items.pop()
          del item
        self.items = None
        if self.model.rowCount() > 0:
          for i in range(0, self.model.rowCount()):
            ritem = self.model.item(i)
            del ritem
          self.model.removeRows(0, self.model.rowCount())
        self.model.modelReset()
        del self.model
        self.model = None
        self.view.reset()
        slicer.modules.NeedleFinderWidget.analysisGroupBoxLayout.removeWidget(self.view)
        del self.view
        self.view = None
        self.initTableView()
        
      # ## Leave the needle detection mode
      widget.fiducialButton.checked = 0
      widget.stop()
      widget.fiducialButton.text = "2. Start Giving Needle Tips"

      # reset button and parameter states
      widget.templateSliceButton.setEnabled(1)
      widget.fiducialButton.setEnabled(0)
      widget.deleteNeedleButton.setEnabled(0)
      widget.resetDetectionButton.setEnabled(0)
      widget.labelMapNode = None
      widget.tempPointList = []
      widget.templateSliceButton.text = "1. Select Current Axial Slice as Seg. Limit (current: None)"
      if not script: widget.onResetParameters()

  def resetNeedleValidation(self):
    """
    Reset the needle validation to completely start over.
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    dialog = qt.QDialog()
    ret = messageBox = qt.QMessageBox.question(dialog, 'Attention', """
      Are you sure that you want to reset the needle validation? 
      It will delete every segmented needles and the control points...
      """, qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    if ret == qt.QMessageBox.Ok:
      self.deleteNeedleValidationModelsFromScene()
      # while slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode') !={}:
        # nodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
        # for node in nodes:
          # slicer.mrmlScene.RemoveNode(node)
      # self.deleteEvaluationNeedlesFromTable()
          
      widget.validationNeedleNumber = 1
      widget.stepNeedle = 0
      self.tableValueCtrPt = [[[999, 999, 999] for i in range(100)] for j in range(100)]
      print "Manual needle validation segmentation reset!" 

  def deleteEvaluationNeedlesFromTable(self):
    """
    Delete all manually segmented needles from report table.
    """
    # productive #onButton
    profprint()
    self.initTableView()
    for name in self.lastNeedleNames:
      print name
      ID = name.lstrip('manual-seg_')
      print "delete validation needle with ID: <%s>" % ID
      try:
        ID = int(ID)
        self.deleteNeedleFromTable(ID)
      except ValueError:
        print "skipping invalid ID"
    
  def changeCursor(self, cursorNumber):
    """
    changes the cursor
    """
    # productive
    profprint()
    appLogic = slicer.app.applicationLogic()
    interactionNode = appLogic.GetInteractionNode()
    interactionNode.SetCurrentInteractionMode(interactionNode.ViewTransform)
    # baseImage = qt.QImage(":/Icons/AnnotationPointWithArrow.png")
    # width =  baseImage.width()
    # height = width
    # center= int(width/2)
    # cursorImage = qt.QImage(width, height, qt.QImage().Format_ARGB32)
    # cursorImage.fill(0)
    # cursorPixmap = qt.QPixmap()
    # cursorPixmap = cursorPixmap.fromImage(cursorImage)
    # cursor = qt.QCursor(cursorPixmap,center,0)

    layoutManager = slicer.app.layoutManager()
    sliceNodeCount = slicer.mrmlScene.GetNumberOfNodesByClass('vtkMRMLSliceNode')
    for nodeIndex in xrange(sliceNodeCount):
      # find the widget for each node in scene
      sliceNode = slicer.mrmlScene.GetNthNodeByClass(nodeIndex, 'vtkMRMLSliceNode')
      sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())
      # sliceWidget.setCursor(cursor)    # doesn't work. Why?
      sliceWidget.setCursor(qt.QCursor(cursorNumber))

  def changeValue(self):
    """Read the value of the Qt widget and select this needle. It is then possible to display sequentially the points used as
     control points of this needle
    """
    # productive #onUpDnArrow
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    widget.scrollPointButton.setText('Scroll Point for Needle ' + str(widget.editNeedleTxtBox.value) + ' (pt: ' + str(self.ptNumber) + ')')

  def scrollPoint(self):
    """Reformat the axial view to display the slice containing the currently selected point.
    """
    # productive #onButton
    profprint()
    self.changeValue()
    widget = slicer.modules.NeedleFinderWidget
    needle = widget.editNeedleTxtBox.value
    # print self.ptNumber
    # print needle
    coord = [0, 0, 0]
    ptName = '.' + str(needle) + '-' + str(self.ptNumber)
    # print ptName
    modelNode = slicer.util.getNode(ptName)
    if modelNode != None:
        self.ptNumber = self.ptNumber + 1
        if modelNode.GetAttribute("ValidationNeedle") == "1":
          modelNode.GetFiducialCoordinates(coord)
          X = coord[0]
          Y = coord[1]
          Z = coord[2]
    
        sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
        if sRed == None :
          sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode1")

        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
        if sYellow == None :
          sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
        
        sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        if sGreen == None :
          sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode3")           

        mYellow = sYellow.GetSliceToRAS()
        mYellow.SetElement(0, 3, X)
        sYellow.Modified()
        sYellow.UpdateMatrices()

        mGreen = sGreen.GetSliceToRAS()
        mGreen.SetElement(1, 3, Y)
        sGreen.Modified()
        sGreen.UpdateMatrices()

        mRed = sRed.GetSliceToRAS()
        mRed.SetElement(2, 3, Z)
        sRed.Modified()
        sRed.UpdateMatrices()
    elif self.ptNumber != 0:
        self.ptNumber = 0
        self.scrollPoint()

  def validationNeedle(self):
    """ When the button 'new validation needle' is pressed, the needle number is incremented, the needle step is reset to
     0

    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    widget.validationNeedleNumber += 1
    widget.validationNeedleButton.text = "New Validation Needle: (" + str(widget.validationNeedleNumber) + ")->(" + str(widget.validationNeedleNumber + 1) + ")"
    # self.tableValueCtrPt.append([])
    widget.stepNeedle = 0

  def filterWithSITK(self):
    """
    Demo method to filter image using SimpleITK.
    See https://github.com/Slicer/Slicer/blob/140b36b50877d85703c094a97fe13303dee570b5/Modules/Scripted/EditorLib/WatershedFromMarkerEffect.py
    """
    # research
    profbox()
    backgroundNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    backgroundNodeName = backgroundNode.GetName()
    backgroundImage = sitk.ReadImage(sitkUtils.GetSlicerITKReadWriteAddress(backgroundNodeName))
    filterImage = sitk.GradientMagnitudeRecursiveGaussian(backgroundImage, float(2));
    del backgroundImage
    sitk.WriteImage(filterImage, sitkUtils.GetSlicerITKReadWriteAddress(backgroundNodeName))
    
    # notify
    backgroundNode.GetImageData().Modified()
    backgroundNode.Modified()
  
  def writeTableHeader(self, fileName, variant=0):
    """
    Write table header to file.
    """
    # research
    w = slicer.modules.NeedleFinderWidget
    l = w.logic
    if not variant:
      l.exportEvaluation(['maxHD', 'avgHD', 'stdHD', 'medHD',
                        'radiusNeedle',
                        'lenghtNeedle',
                        'radiusMax',
                        'numberOfPointsPerNeedle',
                        'nbRotatingIterations',
                        'stepSize',
                        'gradientPonderation',
                        'exponent',
                        'gaussianAttenuationButton',
                        'sigma',
                        'algoV',
                        'case',
                        t.strftime("%d/%m/%Y"), t.strftime("%H:%M:%S")
                        ], fileName)
    else:
      l.exportEvaluation(['HD', 'ID1', 'ID2',
                        'radiusNeedle',
                        'lenghtNeedle',
                        'radiusMax',
                        'numberOfPointsPerNeedle',
                        'nbRotatingIterations',
                        'stepSize',
                        'gradientPonderation',
                        'exponent',
                        'gaussianAttenuationButton',
                        'sigma',
                        'algoV',
                        'case',
                        t.strftime("%d/%m/%Y"), t.strftime("%H:%M:%S")
                        ], fileName)
  
  def parSearch(self, mode=False):
    """
    Parameter evaluation/optimization using no, grid brute-force or random-search algo.
    """
    # research
    profprint()
    w = slicer.modules.NeedleFinderWidget
    l = w.logic
    
    path = [ 0 for i in range(100)]
    path[24] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 24 NRRD/Manual/2013-02-25-Scene-without-CtrPt.mrml'
    path[29] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 29 NRRD/Manual/2013-02-26-Scene-without-CtrPts.mrml'
    path[30] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 30 NRRD/Manual/2013-02-26-Scene-without-CtrPt.mrml'
    path[31] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 31 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'
    path[34] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 34 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'
    path[35] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 35 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'
    path[37] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 37 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'
    path[38] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 38 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'
    path[40] = '/Users/guillaume/Dropbox/AMIGO Gyn Data NRRD/Case 40 NRRD/Manual/2013-02-27-Scene-without-CtrPts.mrml'

    # Andre's file system (cases copies from AMIGO share) MICCAI13 results (LB/AM)
    path = [ 0 for i in range(100)]
    path[24] = '/home/amastmeyer/Pictures/MICCAI13/Case  024/NRRD/Auto-Eval-LB/2013-02-28-Scene.mrml'
    path[28] = '/home/amastmeyer/Pictures/MICCAI13/Case  028/NRRD/Auto-Eval-LB/2013-02-28-Scene.mrml'
    path[29] = '/home/amastmeyer/Pictures/MICCAI13/Case  029/NRRD/Auto-Eval-LB/2013-02-26-Scene.mrml'
    path[30] = '/home/amastmeyer/Pictures/MICCAI13/Case  030/NRRD/Auto-Eval-LB/2013-02-26-Scene.mrml'
    path[31] = '/home/amastmeyer/Pictures/MICCAI13/Case  031/NRRD/Auto-Eval-LB/2013-02-27-Scene.mrml'
    path[33] = '/home/amastmeyer/Pictures/MICCAI13/Case  033/NRRD/Auto-Eval-LB/2013-02-27-Scene.mrml'
    path[34] = '/home/amastmeyer/Pictures/MICCAI13/Case  034/NRRD/Auto-Eval-LB/2013-02-27-Scene.mrml'
    path[37] = '/home/amastmeyer/Pictures/MICCAI13/Case  037/NRRD/Manual Alireza/2013-02-27-Scene.mrml'
    path[38] = '/home/amastmeyer/Pictures/MICCAI13/Case  038/NRRD/Manual Alireza/2013-02-27-Scene.mrml'
    path[40] = '/home/amastmeyer/Pictures/MICCAI13/Case  040/NRRD/Manual Alireza/2013-02-27-Scene.mrml'

    # show a directory selector for saving the results
    self.dirDialog = qt.QFileDialog(w.parent)
    self.dirDialog.setDirectory('/tmp')
    self.dirDialog.options = self.dirDialog.ShowDirsOnly
    self.dirDialog.acceptMode = self.dirDialog.AcceptSave
    #self.dirDialog.show()
    dir=self.dirDialog.getExistingDirectory()
    print "saving results to ", dir
    
    if mode == 0:
      # simple run with current parameters/algo over several patients
      self.writeTableHeader(dir+'/AP-All_stats.csv')
      for id in range(100):
        if path[id]:
          print "processing ", path[id]
          self.writeTableHeader(dir+'/AP-' + str(id) + '.csv', 1)
          slicer.mrmlScene.Clear(0)
          slicer.util.loadScene(path[id])
          # l.resetNeedleDetection(script=True) # ??? this resets the parameters to default
          l.startValidation(script=True)
          results = l.evaluate(script=True)  # calculate HD distances
          l.exportEvaluation(results, dir+'/AP-' + str(id) + '.csv')
          #slicer.util.saveScene(dir+'/AP-' + str(id) + '.mrb') # may use lots of disk space
          # stats
          HD = np.array(results)
          # HD.shape = (int(len(results)/float(3)),3)
          maxHD = HD[:, 0].max()
          avgHD = HD[:, 0].mean()
          stdHD = HD[:, 0].std()
          sl = np.sort(HD[:, 0])
          medHD = sl[sl.size / 2]
          resultsEval = [maxHD, avgHD, stdHD, medHD] + l.valuesExperience + [id]
          l.exportEvaluation(resultsEval, dir+'/AP-All_stats.csv')
          #msgbox("Pause")
          #pause()
      msgbox("parSearch mode 0 done, results in "+dir)
    elif mode == 1:
      id = 'Current'
      # simple brute force search in the dimensions (Guillaumes parameterSearch.py)
      self.writeTableHeader(dir+'/BF-' + str(id) + '.csv', 1)
      self.writeTableHeader(dir+'/BF-' + str(id) + '_stats.csv')
      for i in range(3, 12):
        # l.resetNeedleDetection(script=True) # ??? this resets the parameters to default
        w.numberOfPointsPerNeedle.setValue(i)  # change parameter control points
        l.startValidation(script=True)
        results = l.evaluate(script=True)  # calculate HD distances
        l.exportEvaluation(results, dir+'/BF-' + str(id) + '.csv')
        slicer.util.saveScene(dir+'/BF-' + str(id) + '.mrb') # may use lots of disk space
        # stats
        HD = np.array(results)
        # HD.shape = (int(len(results)/float(3)),3)
        maxHD = HD[:, 0].max()
        avgHD = HD[:, 0].mean()
        stdHD = HD[:, 0].std()
        sl = np.sort(HD[:, 0])
        medHD = sl[sl.size / 2]
        resultsEval = [maxHD, avgHD, stdHD, medHD] + l.valuesExperience
        l.exportEvaluation(resultsEval, dir+'/BF-' + str(id) + '_stats.csv')
        #pause()
      msgbox("parSearch mode 1 done, results in "+dir)
    elif mode == 2:
      # code piece from Guillaumes (bruteForce.py) multi patient mode search  
      for id in range(100):
        if path[id]:
          print "processing ", path[id]
          slicer.mrmlScene.Clear(0)
          slicer.util.loadScene(path[id])
          self.writeTableHeader(dir+'/RS-' + str(id) + '.csv', 1)
          self.writeTableHeader(dir+'/RS-' + str(id) + '_stats.csv')
          for i in range(1, 10000):
            # l.resetNeedleDetection(script=True) # ??? this resets the parameters to default
            w.radiusNeedleParameter.setValue(np.random.randint(1, 6))
            w.stepsize.setValue(np.random.randint(1, 40))
            w.sigmaValue.setValue(np.random.randint(1, 40))  # change parameter sigma
            w.gradientPonderation.setValue(np.random.randint(1, 20))
            w.exponent.setValue(np.random.randint(1, 20))
            w.numberOfPointsPerNeedle.setValue(np.random.randint(3, 11))
            l.startValidation(script=True)
            results = l.evaluate(script=True)  # calculate HD distances
            l.exportEvaluation(results, dir+'/RS-' + str(id) + '.csv')
            slicer.util.saveScene(dir+'/RS-' + str(id) + '.mrb') # may use lots of disk space
            # stats
            HD = np.array(results)
            maxHD = HD[:, 0].max()
            avgHD = HD[:, 0].mean()
            stdHD = HD[:, 0].std()
            sl = np.sort(HD[:, 0])
            medHD = sl[sl.size / 2]
            resultsEval = [maxHD, avgHD, stdHD, medHD] + l.valuesExperience
            l.exportEvaluation(resultsEval, dir+'/RS-' + str(id) + '_stats.csv')
            # end = time.time()
            # print 'processing time: ', end-start
            # start = time.time()
            #pause()
        msgbox("parSearch mode 2 done, results in "+dir)

  #----------------------------------------------------------------------------------------------
  """ Needle segmentation report"""
  #---------------------------------------------------------------------------------------------- 
  
  def initTableView(self):
    """
    Initialize a table gathering information on segmented needles
    Model and view for stats table
    """
    # productive
    profprint()
    if self.table == None:
      # self.keys = ("#")
      # self.keys = ("#","Round" ,"Reliability")
      self.keys = ("#")
      self.labelStats = {}
      self.labelStats['Labels'] = []
      self.items = []
      if self.model == None:
          self.model = qt.QStandardItemModel()
          self.model.setColumnCount(5)
          self.model.setHeaderData(0, 1, "")
          self.model.setHeaderData(1, 1, "#")
          # self.model.setHeaderData(2,1,"R.")
          # self.model.setHeaderData(3,1,"Reliability")
          self.model.setHeaderData(2, 1, "Display")
          self.model.setHeaderData(3, 1, "Reformat")
          self.model.setHeaderData(4, 1, "Comments")
          # self.model.setStrechLastSection(True)
          if self.view == None:
            self.view = qt.QTableView()
            self.view.setMinimumHeight(300)
            self.view.sortingEnabled = True
            self.view.verticalHeader().visible = False
            self.view.horizontalHeader().setStretchLastSection(True)

          # col = 1
          # for k in self.keys:
          #   # self.view.setColumnWidth(col,15*len(k))
          #   # self.model.setHeaderData(col,1,k)
          #   col += 1 
          self.view.setModel(self.model)
          self.view.setColumnWidth(0, 18)
          self.view.setColumnWidth(1, 58)
          self.view.setColumnWidth(2, 58)
          self.table = 1
          self.row = 0
          self.col = 0
          slicer.modules.NeedleFinderWidget.analysisGroupBoxLayout.addRow(self.view)

  def addNeedleToTable(self, ID, label=None, needleType=None):
    """
    Add last segmented needle to the table
    The color icon corresponds to the color of the needle, which corresponds to its label (color code)
    """
    # productive
    profprint()
    self.initTableView()
    if label != None:
      ref = int(label[0]) % MAXNEEDLES
      needleLabel = self.option[ref]
      # reliability = label[1]
    else:
      needleLabel = str(ID)
      ref = ID % MAXNEEDLES
      # reliability = '-'
    # ref = int(modelNode.GetAttribute("nth"))
    
    self.labelStats["Labels"].append(ref)
    self.labelStats[ref, "#"] = needleLabel
    # self.labelStats[ref,"Round"] = str(self.round)
    # self.labelStats[ref,"Reliability"] = str(reliability)

    ################################################
    # Column 0
    color = qt.QColor()
    color.setRgb(self.color255[ref][0], self.color255[ref][1], self.color255[ref][2])
    item = qt.QStandardItem()
    item.setData(color, 1)
    # self.model.appendRow(item)
    self.model.setItem(self.row, 0, item)
    self.items.append(item)
    ################################################
    # Column 1
    self.col = 1
    for k in self.keys:
      item = qt.QStandardItem()
      item.setText(self.labelStats[ref, k])
      self.model.setItem(self.row, self.col, item)
      self.items.append(item)
      self.col += 1
    ################################################
    # Column 2
    displayButton = qt.QPushButton("Display")
    displayButton.checked = True
    displayButton.checkable = True
    if needleType == 'Validation':
      ID = int(slicer.util.getNode('manual-seg_' + str(ID)).GetID().strip('vtkMRMLModelNode'))
    displayButton.connect("clicked()", lambda who=ID: self.displayNeedleTube(who))
    index = self.model.index(self.row, 2)

    self.items.append(displayButton)
    self.col += 1
    self.view.setIndexWidget(index, displayButton)
    ################################################
    # Column 3
    reformatButton = qt.QPushButton("Reformat")
    reformatButton.connect("clicked()", lambda who=ID: self.reformatSagittalView4Needle(who))
    index = self.model.index(self.row, 3)
    self.items.append(reformatButton)
    self.col += 1
    self.view.setIndexWidget(index, reformatButton)
    ################################################
    # Column 4
    editField = qt.QTextEdit("")
    index = self.model.index(self.row, 4)
    self.items.append(editField)
    self.col += 1
    self.view.setIndexWidget(index, editField)

    self.row += 1  
  
  def deleteNeedleFromTable(self, ID):
    """
    Delete last needle from model
    """
    profprint()
    # productive #onButton
    print "len(items): ", len(self.items)
    if self.row:
      pos = self.labelStats["Labels"].index(ID)
      ref = ID % MAXNEEDLES
      self.labelStats["Labels"].pop(pos)
      self.labelStats[ref, "Label"] = None
      # self.labelStats[ref,"Round"] = None
      # self.labelStats[ref,"Reliability"] = None
      pos += 1
      for i in range(1, self.col + 1):
        item = self.items.pop(pos * self.col - i)
        del item
      pos -= 1
      ritem = self.model.item(pos)
      del ritem
      self.model.removeRow(pos)
      self.row -= 1

  #-----------------------------------------------------------
  # Radiation

  def AddRadiation(self, i, needleID):
    """
    Goal of this function is to draw quadrics simulating the dose radiation.
    Currently, ellipse is a too naive model.
    This project might be continued later
    """
    # obsolete
    profbox()
    pass
    # needleNode = slicer.mrmlScene.GetNodeByID(needleID)
    # polyData = needleNode.GetPolyData()
    # nb = polyData.GetNumberOfPoints()
    # base = [0,0,0]
    # tip = [[0,0,0] for k in range(11)]
    # if nb>100:
      
      # polyData.GetPoint(nb-1,tip[10])
      # polyData.GetPoint(0,base)
    
    # a = tip[10][0]-base[0]
    # b = tip[10][1]-base[1]
    # c = tip[10][2]-base[2]
    
    # for l in range(7):
      # tip[9-l][0] = tip[10][0]-0.1*a*(l+1)
      # tip[9-l][1] = tip[10][1]-0.1*b*(l+1)
      # tip[9-l][2] = tip[10][2]-0.1*c*(l+1)
    # for l in range(1,3):
      # tip[l][0] = tip[10][0]+0.1*a*l
      # tip[l][1] = tip[10][1]+0.1*b*l
      # tip[l][2] = tip[10][2]+0.1*c*l
         
    # rad = vtk.vtkAppendPolyData()  
    
    # for l in range(1,11):
      # TransformPolyDataFilter=vtk.vtkTransformPolyDataFilter()
      # Transform=vtk.vtkTransform()        
      # TransformPolyDataFilter.SetInput(self.m_polyRadiation)

      # vtkmat = Transform.GetMatrix()
      # vtkmat.SetElement(0,3,tip[l][0])
      # vtkmat.SetElement(1,3,tip[l][1])
      # vtkmat.SetElement(2,3,tip[l][2])
      # TransformPolyDataFilter.SetTransform(Transform)
      # TransformPolyDataFilter.Update()
    
      # rad.AddInput(TransformPolyDataFilter.GetOutput())
    
    # modelNode = slicer.vtkMRMLModelNode()
    # displayNode = slicer.vtkMRMLModelDisplayNode()
    # storageNode = slicer.vtkMRMLModelStorageNode()
 
    # fileName = 'Rad'+self.option[i]+'.vtk'

    # mrmlScene = slicer.mrmlScene
    # modelNode.SetName(fileName)
    # modelNode.SetAttribute("radiation","segmented")
    # modelNode.SetAttribute("needleID",str(needleID))    
    # modelNode.SetAndObservePolyData(rad.GetOutput()) 

    # modelNode.SetScene(mrmlScene)
    # storageNode.SetScene(mrmlScene)
    # storageNode.SetFileName(fileName)  
    # displayNode.SetScene(mrmlScene)
    # displayNode.SetVisibility(0)
    # mrmlScene.AddNode(storageNode)
    # mrmlScene.AddNode(displayNode)
    # mrmlScene.AddNode(modelNode)
    # modelNode.SetAndObserveStorageNodeID(storageNode.GetID())
    # modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
    
    # displayNode.SetPolyData(modelNode.GetPolyData())

    # displayNode.SetSliceIntersectionVisibility(0)
    # displayNode.SetScalarVisibility(1)
    # displayNode.SetActiveScalarName('scalars')
    # displayNode.SetScalarRange(0,230)
    # displayNode.SetOpacity(0.06)
    # displayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileHotToColdRainbow.txt')
    # displayNode.SetBackfaceCulling(0)
    # pNode= self.parameterNode()
    # pNode.SetParameter(fileName,modelNode.GetID())
    # mrmlScene.AddNode(modelNode)
    
  #----------------------------------------------------------------------------------------------
  """
  The purpose of the following functions is to process the results of the needle segmentation from 
  Yi Gao's CLI module.
  Currently, another solution has been chosen but this could be usefull again later.
  To use it, simply uncommented the corresponding buttons in "createUserInterface"
  """
  #----------------------------------------------------------------------------------------------
  
  def needleSegmentationCLIDEMO(self):
    """
    Function used for the CLI module from Yi Gao using hessian filter (C++)
    """
    # research
    profbox()
    widget = slicer.modules.NeedleFinderWidget
    scene = slicer.mrmlScene
    pNode = self.parameterNode()
    if slicer.mrmlScene.GetNodeByID(pNode.GetParameter("baselineVolumeID")) == None:
      inputVolume = self.__volumeSelector.currentNode()
      inputVolumeID = self.__volumeSelector.currentNode().GetID()
    else:
      inputVolume = slicer.mrmlScene.GetNodeByID(pNode.GetParameter("baselineVolumeID"))
      inputVolumeID = slicer.mrmlScene.GetNodeByID(pNode.GetParameter("baselineVolumeID")).GetID()
    inputLabelID = self.__needleLabelSelector.currentNode().GetID()
    
    datetime = time.strftime("%Y-%m-%d-%H_%M_%S", time.localtime())
    
    inputVolume.SetAttribute("foldername", datetime)
    self.outputVolumeNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLModelNode')
    self.outputVolumeNode.SetName("Output Needle Model")
    outputVolumeStorageNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLModelStorageNode')
    slicer.mrmlScene.AddNode(self.outputVolumeNode)
    slicer.mrmlScene.AddNode(outputVolumeStorageNode)
    self.outputVolumeNode.AddAndObserveStorageNodeID(outputVolumeStorageNode.GetID())
    outputVolumeStorageNode.WriteData(self.outputVolumeNode)
    
    outputID = self.outputVolumeNode.GetID()
    
    self.foldername = '/NeedleModels/' + datetime
    
    # Set the parameters for the CLI module    
    parameters = {} 
    parameters['inputVolume'] = inputVolumeID
    parameters['inputLabel'] = inputLabelID
    parameters['outputVtk'] = outputID
    parameters['outputFolderName'] = self.foldername
    parameters['nbPointsPerLine'] = self.nbPointsPerLine.value
    parameters['nbRadiusIterations'] = self.nbRadiusIterations.value
    parameters['radiusMax'] = self.radiusMax.value
    parameters['numberOfPointsPerNeedle'] = self.numberOfPointsPerNeedle.value
    parameters['nbRotatingIterations'] = self.nbRotatingIterations.value
    
    module = slicer.modules.mainlabelneedletrackingcli 
    self.__cliNode = None
    self.__cliNode = slicer.cli.run(module, None, parameters, wait_for_completion=True)
        
    ##### match the needles ######

    self.setNeedleCoordinates()
    self.computerPolydataAndMatrix()
    xmin = min(self.p[0])
    xmax = max(self.p[0])
    ymin = min(self.p[1])
    ymax = max(self.p[1])
    xdelta = xmax - xmin
    ydelta = ymax - ymin
    k = 0

    self.base = [[0 for j in range(3)] for j in range(63)]
    self.tip = [[0 for j in range(3)] for j in range(63)]
    self.needlenode = [[0 for j in range(2)] for j in range(63)]
    self.bentNeedleNode = [[0 for j in range(2)] for j in range(63)]
    self.displaynode = [0 for j in range(63)]
    self.displaynodeB = [0 for j in range(63)]
    self.fiducialnode = [0 for j in range(63)]
    
    for i in xrange(63):

      pathneedle = self.foldername + '/' + str(i) + '.vtp'
      pathBentNeedle = self.foldername + '/' + str(i) + '_bent.vtp'
      self.needlenode[i] = slicer.util.loadModel(pathneedle, True)
      self.bentNeedleNode[i] = slicer.util.loadModel(pathBentNeedle, True)

      if self.needlenode[i][0] == True and self.needlenode[i][1] != None:
        self.displaynode[i] = self.needlenode[i][1].GetDisplayNode()
        self.displaynodeB[i] = self.bentNeedleNode[i][1].GetDisplayNode()

         
        polydata = self.needlenode[i][1].GetPolyData()
        polydata.GetPoint(0, self.base[i])        
      
        self.displaynode[i].SliceIntersectionVisibilityOn()
        self.displaynodeB[i].SliceIntersectionVisibilityOn()
        bestmatch = None
        mindist = None
        for j in xrange(63):
          delta = ((self.p[0][j] - (self.base[i][0])) ** 2 + (self.p[1][j] - self.base[i][1]) ** 2) ** (0.5)
          if delta < mindist or mindist == None:
            bestmatch = j
            mindist = delta
        
        bestmatch = k
        k += 1
        self.displaynode[i].SetColor(self.color[bestmatch])
        self.displaynodeB[i].SetColor(self.color[bestmatch])
        self.needlenode[i][1].SetName(self.option[bestmatch] + "_segmented")
        self.bentNeedleNode[i][1].SetName(self.option[bestmatch] + "_optimized")
        self.needlenode[i][1].SetAttribute("segmented", "1")
        self.bentNeedleNode[i][1].SetAttribute("optimized", "1")
        self.needlenode[i][1].SetAttribute("nth", str(bestmatch))
        self.bentNeedleNode[i][1].SetAttribute("nth", str(bestmatch))
        self.needlenode[i][1].SetAttribute("needleID", self.needlenode[i][1].GetID())
        self.bentNeedleNode[i][1].SetAttribute("needleID", self.bentNeedleNode[i][1].GetID())
 
    if widget.removeDuplicates.isChecked():
      self.positionFilteringNeedles()

    d = slicer.mrmlScene.GetNodeByID(outputID).GetDisplayNode()
    d.SetVisibility(0)
    
    self.__editorFrame.collapsed = 1
    
    self.addButtons()
  
  def addButtons(self):
    """Buttons for the reporting widget, displaying information of the segmented needles.
    Used in conjunction with Yi Gaos CLI stuff.
    """
    profbox()
    if self.buttonsGroupBox != None:
      self.layout.removeWidget(self.buttonsGroupBox)
      self.buttonsGroupBox.deleteLater()
      self.buttonsGroupBox = None
    self.buttonsGroupBox = qt.QGroupBox()
    self.buttonsGroupBox.setTitle('Manage Needles')
    self.layout.addRow(self.buttonsGroupBox)
    self.buttonsGroupBoxLayout = qt.QFormLayout(self.buttonsGroupBox)
    
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("segmented") == "1":
        i = int(modelNode.GetAttribute("nth"))
        buttonDisplay = qt.QPushButton("Hide " + self.option[i])
        buttonBentDisplay = qt.QPushButton("Hide Bent " + self.option[i])
        buttonDisplay.checkable = True
        buttonBentDisplay.checkable = True

        if modelNode.GetDisplayVisibility() == 0:
          buttonDisplay.setChecked(1)

        buttonDisplay.connect("clicked()", lambda who=i: self.displayNeedle(who))
        buttonBentDisplay.connect("clicked()", lambda who=i: self.displayBentNeedle(who))
        buttonReformat = qt.QPushButton("Reformat " + self.option[i])
        buttonReformat.connect("clicked()", lambda who=i: self.reformatNeedle(who))
        widgets = qt.QWidget()
        hlay = qt.QHBoxLayout(widgets)
        hlay.addWidget(buttonDisplay)
        hlay.addWidget(buttonBentDisplay)
        hlay.addWidget(buttonReformat)
        self.buttonsGroupBoxLayout.addRow(widgets)
  
  def displayBentNeedle(self, i):
    """
    not actively used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    """
    profbox()
    # obsolete
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth") == str(i) and modelNode.GetAttribute("optimized") == '1' :
        displayNode = modelNode.GetModelDisplayNode()
        nVisibility = displayNode.GetVisibility()
        # print nVisibility
        if nVisibility:
          displayNode.SliceIntersectionVisibilityOff()
          displayNode.SetVisibility(0)
        else:
          displayNode.SliceIntersectionVisibilityOn()
          displayNode.SetVisibility(1)
  
  def displayNeedle(self, i):
    """
    ??? not used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    """
    # obsolete
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth") == str(i) and modelNode.GetAttribute("segmented") == '1' :
        displayNode = modelNode.GetModelDisplayNode()
        nVisibility = displayNode.GetVisibility()
       
        if nVisibility:
          displayNode.SliceIntersectionVisibilityOff()
          displayNode.SetVisibility(0)
        else:
          displayNode.SliceIntersectionVisibilityOn()
          displayNode.SetVisibility(1)
      
  def showOneNeedle(self, i, visibility):
    """
    ??? Not used anymore. But can be usefull later
    """
    # obsolete
    profbox()
    fidname = "fid" + self.option[i]
    pNode = self.parameterNode()
    needleID = pNode.GetParameter(self.option[i] + '.vtp')
    fidID = pNode.GetParameter(fidname)    
    NeedleNode = slicer.mrmlScene.GetNodeByID(needleID)
    fiducialNode = slicer.mrmlScene.GetNodeByID(fidID)    
    
    if NeedleNode != None:
      displayNode = NeedleNode.GetModelDisplayNode()
      nVisibility = displayNode.GetVisibility()  

      if fiducialNode == None:
        displayNode.SetVisibility(1)    
        displayNode.SetOpacity(0.9)
        polyData = NeedleNode.GetPolyData()
        polyData.Update()
        nb = int(polyData.GetNumberOfPoints() - 1)
        coord = [0, 0, 0]
        if nb > 100:
          fiducialNode = slicer.vtkMRMLAnnotationFiducialNode()
          polyData.GetPoint(nb, coord)    
          fiducialNode.SetName(self.option[i])
          fiducialNode.SetFiducialCoordinates(coord)         
          fiducialNode.Initialize(slicer.mrmlScene)
          fiducialNode.SetLocked(1)
          fiducialNode.SetSelectable(0)
          fidDN = fiducialNode.GetDisplayNode()
          fidDN.SetColor(NeedleNode.GetDisplayNode().GetColor())
          fidDN.SetGlyphScale(0)
          fidTN = fiducialNode.GetAnnotationTextDisplayNode()
          fidTN.SetTextScale(3)
          fidTN.SetColor(NeedleNode.GetDisplayNode().GetColor())
          fiducialNode.SetDisplayVisibility(0)
          pNode.SetParameter(fidname, fiducialNode.GetID())
          fiducialNode.SetDisplayVisibility(1)

      if visibility == 0:

        displayNode.SetVisibility(0)
        displayNode.SetSliceIntersectionVisibility(0)
        if fiducialNode != None:
          fiducialNode.SetDisplayVisibility(0)

      else:

        displayNode.SetVisibility(1)
        displayNode.SetSliceIntersectionVisibility(1)
        if fiducialNode != None:
          fiducialNode.SetDisplayVisibility(1)

    else:
      vtkmat = vtk.vtkMatrix4x4()
      vtkmat.DeepCopy(self.m_vtkmat)
      vtkmat.SetElement(0, 3, self.m_vtkmat.GetElement(0, 3) + self.p[0][i])
      vtkmat.SetElement(1, 3, self.m_vtkmat.GetElement(1, 3) + self.p[1][i])
      vtkmat.SetElement(2, 3, self.m_vtkmat.GetElement(2, 3) + (30.0 - 150.0) / 2.0)

      TransformPolyDataFilter = vtk.vtkTransformPolyDataFilter()
      Transform = vtk.vtkTransform()        
      TransformPolyDataFilter.SetInput(self.m_polyCylinder)
      Transform.SetMatrix(vtkmat)
      TransformPolyDataFilter.SetTransform(Transform)
      TransformPolyDataFilter.Update()

      triangles = vtk.vtkTriangleFilter()
      triangles.SetInput(TransformPolyDataFilter.GetOutput())  
      self.AddModel(i, triangles.GetOutput())
      self.showOneNeedle(i, visibility)
            
  def AddModel(self, i, polyData):
    """
    Not used. Check if can be removed
    """
    # obsolete
    profbox()
    modelNode = slicer.vtkMRMLModelNode()
    displayNode = slicer.vtkMRMLModelDisplayNode()
    storageNode = slicer.vtkMRMLModelStorageNode()
 
    fileName = self.option[i] + '.vtp'

    mrmlScene = slicer.mrmlScene
    modelNode.SetName(fileName)  
    modelNode.SetAndObservePolyData(polyData)
    modelNode.SetAttribute("planned", "1")
    
    mrmlScene.SaveStateForUndo()
    modelNode.SetScene(mrmlScene)
    storageNode.SetScene(mrmlScene)
    storageNode.SetFileName(fileName)  
    displayNode.SetScene(mrmlScene)
    displayNode.SetVisibility(1)
    mrmlScene.AddNode(storageNode)
    mrmlScene.AddNode(displayNode)
    mrmlScene.AddNode(modelNode)
    modelNode.SetAndObserveStorageNodeID(storageNode.GetID())
    modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
    
    displayNode.SetColor(self.color[i])
    displayNode.SetSliceIntersectionVisibility(0)
    pNode = self.parameterNode()
    pNode.SetParameter(fileName, modelNode.GetID())
    mrmlScene.AddNode(modelNode)
    displayNode.SetVisibility(1)

  def displayRadPlanned(self):
    """
    Display 'radiation' of planned needle -> cf iGyne / not used anymore
    """
    # obsolete?
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      displayNode = modelNode.GetDisplayNode()
      if modelNode.GetAttribute("radiation") == "planned":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode.GetDisplayVisibility() == 1:
          modelNode.SetDisplayVisibility(abs(int(slicer.modules.NeedleFinderWidget.displayRadPlannedButton.checked) - 1))
            
  def displayRadSegmented(self):
    """
    Display 'radiation' of segmented needles
    ??? used?
    """
    # obsolete?
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("radiation") == "segmented":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility() == 1:
            modelNode.SetDisplayVisibility(abs(int(slicer.modules.NeedleFinderWidget.displayRadSegmentedButton.checked) - 1))
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(abs(int(slicer.modules.NeedleFinderWidget.displayRadSegmentedButton.checked) - 1))
            
  def displayContour(self, i, visibility):
    """
    Display the iso-contour of needle i

    :param i: nth value of needle
    :param visibility: boolean to set the visibility state of the needle
    ??? used?
    """
    # obsolete?
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("contour") == "1" and modelNode.GetAttribute("nth") == str(i) :
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility() == 1:
            modelNode.SetDisplayVisibility(visibility)
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(visibility)
            
  def displayContours(self):
    """
    Display or hide the iso-contours of every needles
    ??? used?
    """
    # obsolete?
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("contour") == "1":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility() == 1:
            modelNode.SetDisplayVisibility(abs(int(slicer.modules.NeedleFinderWidget.displayContourButton.checked) - 1))
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(abs(int(slicer.modules.NeedleFinderWidget.displayContourButton.checked) - 1)) 

  def displayFiducial(self):
    """
    ??? used? show labels of the needles by adding a fiducial point at the tip
    """
    # obsolete?
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      displayNode = modelNode.GetDisplayNode()
      if modelNode.GetAttribute("segmented") == "1" and modelNode.GetAttribute("nth") != None:
        if 1:
          i = int(modelNode.GetAttribute("nth"))
          if self.fiducialnode[i] == 0:    
            polyData = modelNode.GetPolyData()
            nb = int(polyData.GetNumberOfPoints() - 1)
            coord = [0, 0, 0]
            if nb > 10:
              self.fiducialnode[i] = slicer.vtkMRMLAnnotationFiducialNode()
              polyData.GetPoint(nb, coord)    
              self.fiducialnode[i].SetName(self.option[i])
              self.fiducialnode[i].SetFiducialCoordinates(coord)         
              self.fiducialnode[i].Initialize(slicer.mrmlScene)
              self.fiducialnode[i].SetLocked(1)
              self.fiducialnode[i].SetSelectable(0)
              fidDN = self.fiducialnode[i].GetDisplayNode()
              fidDN.SetColor(modelNode.GetDisplayNode().GetColor())
              fidDN.SetGlyphScale(0)
              fidTN = self.fiducialnode[i].GetAnnotationTextDisplayNode()
              fidTN.SetTextScale(3)
              fidTN.SetColor(modelNode.GetDisplayNode().GetColor())
              
              self.fiducialnode[i].SetDisplayVisibility(modelNode.GetDisplayNode().GetVisibility())
          else:    
            if modelNode.GetDisplayNode().GetVisibility():
               self.fiducialnode[i].SetDisplayVisibility(abs(self.fiducialnode[i].GetDisplayVisibility() - 1))
            if self.fiducialnode[i].GetDisplayVisibility() == 1:
              self.displayFiducialButton.text = "Hide Labels on Needles"
            else:
              self.displayFiducialButton.text = "Display Labels on Needles" 

  def reformatNeedle(self, ID):
    """
    ??? used? Reformat the sagittal view to be tangent to the needle
    """
    # obsolete?
    profprint() 
    modelNode = slicer.util.getNode('vtkMRMLModelNode' + str(ID))
    polyData = modelNode.GetPolyData()
    nb = polyData.GetNumberOfPoints()
    base = [0, 0, 0]
    tip = [0, 0, 0]
    polyData.GetPoint(nb - 1, tip)
    polyData.GetPoint(0, base)
    a, b, c = tip[0] - base[0], tip[1] - base[1], tip[2] - base[2]
    
    sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
    if sYellow == None :
      sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")        
    reformatLogic = slicer.vtkSlicerReformatLogic()
    sYellow.SetSliceVisible(1)
    reformatLogic.SetSliceNormal(sYellow, 1, -a / b, 0)
    m = sYellow.GetSliceToRAS()
    m.SetElement(0, 3, base[0])
    m.SetElement(1, 3, base[1])
    m.SetElement(2, 3, base[2])
    sYellow.Modified()

  def drawIsoSurfaces0(self):
    """
    ??? used? for development purposes.
    This shall indicate radiation influence zones.
    Ellipsoid at tip of the needel.
    """
    # research
    profbox()
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    v = vtk.vtkAppendPolyData()
    
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth") != None and modelNode.GetDisplayVisibility() == 1 :
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
  
  #----------------------------------------------------------------------------------------------
  """
  End of the functions used with the Yi's CLI module
  """
  #----------------------------------------------------------------------------------------------
  #----------------------------------------------------------------------------------------------
  """
  Functions for validation study 
  """
  #----------------------------------------------------------------------------------------------
  
  def returnTipsFromNeedleModels(self):
    """ Returns the IJK coordinates of the tips of manually segmented needle polygon models

    :return: array of IJK coordinates of validation needle tips
    """
    # productive
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    returnTips = []
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
    nbNode = modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
        # print nthNode
        node = slicer.mrmlScene.GetNthNodeByClass(nthNode, 'vtkMRMLModelNode')
        if node.GetAttribute('type') == 'Validation':
            polydata = node.GetPolyData()
            p, pbis = [0, 0, 0], [0, 0, 0]
            if polydata.GetNumberOfPoints() > 100:  # ??? this is risky when u have other models in the scene (not only neeedles(
                if not widget.autoStopTip.isChecked():
                  polydata.GetPoint(0, p)
                  polydata.GetPoint(int(polydata.GetNumberOfPoints() - 1), pbis)
                  if pbis[2] > p[2]:
                      p = pbis
                else:
                  # get a point from the middle of the needle shaft polygon model
                  polydata.GetPoint(int(polydata.GetNumberOfPoints() / 2), p)
                returnTips.append(self.ras2ijk(p))
    return returnTips

  def startValidation(self, script=False):
    """Start the evaluation process:
    * Calls returnTipsFromNeedleModels() to build an array of the tip of manually segmented needles
    * Use theses tips to generate auto segmented needles
    * Calls evaluate() to compute the Hausdorff's distance between every pair of needles

    :return: print the results in the python interactor (CMD+3 or CTRL+3)
    """
    # productive #button
    print "\n"*100
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    self.deleteNeedleDetectionModelsFromScene()
    tips = self.returnTipsFromNeedleModels()
    # delete old needles as they will be recalculated
    self.deleteAllAutoNeedlesFromScene()
    # select the image node from the Red slice viewer
    m = vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    spacing = volumeNode.GetSpacing()
    # chrono starts
    self.t0 = time.clock()

    for i in range(len(tips)):
      A = tips[i]
      colorVar = i  # ??? /(len(tips))
      self.needleDetectionThread(A, imageData, colorVar, spacing, script)
      if widget.autoStopTip.isChecked():
        self.needleDetectionUPThread(A, imageData, colorVar, spacing, script)

    # print tips
    if script == False:
        t = self.evaluate()
        print '--------------------------'
        print 'New HD Validation Results:'
        print 'i\tman.-seg_\tHD [mm]'
        for i in range(len(t)):
            print i,'\t', slicer.util.getNode("vtkMRMLModelNode"+str(int(t[i][1]))).GetName().strip("manual-seg_"),'\t',t[i][0]
        print '=========================='
  def placeAxialLimitMarker(self, assign=True):
    """
    Get the K (of IJK) value of the current axial slice. 
    Used to define the slice containing the template
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    if assign:
      # remove old nodes from scene
      while slicer.util.getNodes('template slice position*') != {}:
        nodes = slicer.util.getNodes('template slice position*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)
  
      s = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetSliceNode()
      offSet = s.GetSliceOffset()
      rasVector = [0, 0, offSet]
      widget.templateSliceButton.text = "1. Select Current Axial Slice as Seg. Limit (current: " + str(offSet) + ")"
  
      widget.axialSegmentationLimit = int(round(self.ras2ijk(rasVector)[2]))
  
      self.fiducialNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      self.fiducialNode.Initialize(slicer.mrmlScene)
      self.fiducialNode.SetName('template slice position')        
      self.fiducialNode.SetFiducialCoordinates(rasVector)
      fd = self.fiducialNode.GetDisplayNode()
      fd.SetVisibility(1)
      fd.SetColor([0, 1, 0])
      widget.fiducialButton.setEnabled(1)
    # here we are set and can create a first label volume from volume data
    widget.createAddOrSelectLabelMapNode()

    # ## Add crosshair
    crosshairNode = slicer.util.getNode("Crosshair")
    crosshairNode.SetCrosshairMode(slicer.vtkMRMLCrosshairNode().ShowIntersection)

  def exportEvaluation(self, results, url):
    """ Export evaluation results to a CSV file (e.g. when doing parameter optimizations)

    :param results: array containing the results of the evaluation
    :param url: url for saving the file
    """
    # research
    profprint()
    if not os.path.exists(url):
      print "creating new results file: ",url
      open(url, 'w').close()
    myfile = open(url, 'a')

    wr = csv.writer(myfile)
    r = numpy.array(results)
    if len(r.shape) == 1:
      wr.writerow(results)
    else:
      wr.writerows(results)

  def hausdorffDistance(self, id1, id2):
    """
    Calculates the Hausdorff's distance [HD]_ of two needles. Both needles are truncated to start and end at the same slices.

    :param id1: vtkMRMLModelNodeID of Needle 1
    :param id2: vtkMRMLModelNodeID of Needle 2
    :return: Hausdorff's distance in millimeters

    .. math::  d_{\mathrm H}(X,Y) = \max\{\,\sup_{x \in X} \inf_{y \in Y} d(x,y),\, \sup_{y \in Y} \inf_{x \in X} d(x,y)\,\}

    .. image:: http://upload.wikimedia.org/wikipedia/commons/2/21/Hausdorff_distance_sample.svg
           :height: 300px
           :width: 500 px
           :scale: 100 %
           :alt: alternate text
           :align: center

    .. [HD] http://en.wikipedia.org/wiki/Hausdorff_distance
    """
    # productive #math
    profprint()
    node1 = slicer.mrmlScene.GetNodeByID(id1)
    polydata1 = node1.GetPolyData()
    node2 = slicer.mrmlScene.GetNodeByID(id2)
    polydata2 = node2.GetPolyData()
    nb1 = polydata1.GetNumberOfPoints()
    nb2 = polydata2.GetNumberOfPoints()
    minimum = None
    maximum = None
    JJ, jj = None, None
    II, ii = None, None
    pt1 = [0, 0, 0]
    pt2 = [0, 0, 0]
    polydata1.GetPoint(1, pt1)
    polydata1.GetPoint(nb1 - 1, pt2)
    minVal1 = min(pt1[2], pt2[2])
    maxVal1 = max(pt1[2], pt2[2])
    pt1 = [0, 0, 0]
    pt2 = [0, 0, 0]
    pt1b, pt2b = None, None
    polydata2.GetPoint(1, pt1)
    polydata2.GetPoint(nb2 - 1, pt2)
    minVal2 = min(pt1[2], pt2[2])
    maxVal2 = max(pt1[2], pt2[2])
    valueBase = max(minVal1, minVal2)
    valueTip = min(maxVal1, maxVal2)

    # truncate polydatas
    truncatedPolydata1 = self.clipPolyData(node1, valueBase)
    truncatedPolydata2 = self.clipPolyData(node2, valueBase)

    cellId = vtk.mutable(1)
    subid = vtk.mutable(1)
    dist = vtk.mutable(1)
    cl2 = vtk.vtkCellLocator()
    cl2.SetDataSet(truncatedPolydata2)
    cl2.BuildLocator()
    # Hausforff 1 -> 2
    minima = []
    for i in range(int(nb1 / float(10))):
      pt = [0, 0, 0]
      polydata1.GetPoint(10 * i, pt)
      closest = [0, 0, 0]
      cl2.FindClosestPoint(pt, closest, cellId, subid, dist)
      if abs(closest[2] - pt[2]) <= 1:
        minima.append(self.distance(pt, closest))
      else:
          minima.append(0)
    hausdorff12 = max(minima)
    
    # Hausforff 2 -> 1
    minima = []
    cl1 = vtk.vtkCellLocator()
    cl1.SetDataSet(truncatedPolydata1)
    cl1.BuildLocator()
    for i in range(int(nb2 / float(10))):
      pt = [0, 0, 0]
      polydata2.GetPoint(10 * i, pt)
      closest = [0, 0, 0]
      cl1.FindClosestPoint(pt, closest, cellId, subid, dist)
      if abs(closest[2] - pt[2]) <= 1:
        minima.append(self.distance(pt, closest))
      else:
          minima.append(0)
    hausdorff21 = max(minima)
    return max(hausdorff12, hausdorff21)
  
  def hausdorffDistance13(self, id1, id2):
    """MICCAI13 Version
    iGyne_old 4450bbcb543e7432122f06c1905aab4eb8b446e6
    """
    # productive #math
    profprint()
    node1 = slicer.mrmlScene.GetNodeByID(id1)
    polydata1 = node1.GetPolyData()
    node2 = slicer.mrmlScene.GetNodeByID(id2)
    polydata2 = node2.GetPolyData()
    nb1 = polydata1.GetNumberOfPoints()
    nb2 = polydata2.GetNumberOfPoints()
    minimum = None
    maximum = None
    JJ, jj = None, None
    II, ii = None, None
    pt1 = [0, 0, 0]
    pt2 = [0, 0, 0]
    polydata1.GetPoint(1, pt1)
    polydata1.GetPoint(nb1 - 1, pt2)
    minVal1 = min(pt1[2], pt2[2])
    maxVal1 = max(pt1[2], pt2[2])
    pt1 = [0, 0, 0]
    pt2 = [0, 0, 0]
    pt1b, pt2b = None, None
    polydata2.GetPoint(1, pt1)
    polydata2.GetPoint(nb2 - 1, pt2)
    minVal2 = min(pt1[2], pt2[2])
    maxVal2 = max(pt1[2], pt2[2])
    valueBase = max(minVal1, minVal2)
    valueTip = min(maxVal1, maxVal2)
    cellId = vtk.mutable(1)
    subid = vtk.mutable(1)
    dist = vtk.mutable(1)
    cl2 = vtk.vtkCellLocator()
    cl2.SetDataSet(polydata2)
    cl2.BuildLocator()
    # Hausforff 1 -> 2
    minima = []
    for i in range(int(nb1 / float(100))):
      pt = [0, 0, 0]
      polydata1.GetPoint(100 * i, pt)
      closest = [0, 0, 0]
      cl2.FindClosestPoint(pt, closest, cellId, subid, dist)
      if abs(closest[2] - pt[2]) <= 1:
        minima.append(self.distance(pt, closest))
      else:
          minima.append(0)
    hausdorff12 = max(minima)
    
    # Hausforff 2 -> 1
    minima = []
    cl1 = vtk.vtkCellLocator()
    cl1.SetDataSet(polydata1)
    cl1.BuildLocator()
    for i in range(int(nb2 / float(10))):
      pt = [0, 0, 0]
      polydata2.GetPoint(10 * i, pt)
      closest = [0, 0, 0]
      cl1.FindClosestPoint(pt, closest, cellId, subid, dist)
      if abs(closest[2] - pt[2]) <= 1:
        minima.append(self.distance(pt, closest))
      else:
          minima.append(0)
    hausdorff21 = max(minima)
    return max(hausdorff12, hausdorff21)

  def evaluate(self, script=False):
    """
    This function first invokes needleMatching() with, for each automatically segmented needle in the vtkMRMLScene,
    associates it with its manually segmented version.
    Then, the HD is computed between each pairs of needle and the results are reported in a numpy array

    :return numpy array of [ value , ID needle 1, ID needle 2 ]
    """
    # productive
    profprint()
    result = self.needleMatching()
    HD = []
    widget = slicer.modules.NeedleFinderWidget
    self.valuesExperience = [ widget.radiusNeedleParameter.value,
                            widget.lenghtNeedleParameter.value,
                            widget.radiusMax.value,
                            widget.numberOfPointsPerNeedle.value,
                            widget.nbRotatingIterations.value,
                            widget.stepsize.value,
                            widget.gradientPonderation.value,
                            widget.exponent.value,
                            widget.gaussianAttenuationButton.isChecked() * 1,
                            widget.sigmaValue.value,
                            widget.algoVersParameter.value]

    for i in range(len(result)):
      if widget.algoVersParameter.value == 0:
        val = self.hausdorffDistance(result[i][1], result[i][2])
      else:
        val = self.hausdorffDistance13(result[i][1], result[i][2])
      if script == True:
        results = [float(val), int(result[i][1].strip('vtkMRMLModelNode')), int(result[i][2].strip('vtkMRMLModelNode'))] + self.valuesExperience
      else:
        results = [float(val), int(result[i][1].strip('vtkMRMLModelNode')), int(result[i][2].strip('vtkMRMLModelNode'))]
      HD.append(results)
    if script == False:
      return numpy.array(HD).astype(numpy.double)
    else:
      return HD

  def distTip(self, id1, id2):
    """ Returns the axial distance between the tip of two needles

    :param id1: ID number for the needle 1 (vtkMRMLModelNode)
    :param id2: ID number for the needle 2 (vtkMRMLModelNode)
    :return: distance in millimeters between the tip of both needles
    """
    # productive #math
    profprint()
    node = slicer.mrmlScene.GetNodeByID('vtkMRMLModelNode' + str(id1))
    polydata = node.GetPolyData()
    node2 = slicer.mrmlScene.GetNodeByID('vtkMRMLModelNode' + str(id2))
    polydata2 = node2.GetPolyData()
    p, pbis = [0, 0, 0], [0, 0, 0]
    p2 = [0, 0, 0]
    p2bis = [0, 0, 0]
    axialDistance = []
    for i in range(100):
        polydata.GetPoint(i, p)
        polydata.GetPoint(2499 - i, pbis)
        if pbis[2] > p[2]:
          p = pbis
        polydata2.GetPoint(2499 - i, p2)
        polydata2.GetPoint(i, p2bis)
        if p2bis[2] > p2[2]:
          p2 = p2bis
        axialDistance.append(((p2[0] - p[0]) ** 2 + (p2[1] - p[1]) ** 2 + (p2[2] - p[2]) ** 2) ** 0.5)
    return min(axialDistance)

  def needleMatching(self):
    """This functions associates manually segmented needles to their automatically segmented version. To do so,
    each manually segmented needle has a 'type' attribute named 'validation'. For each manually segmented needle, an axial
    distance between the tip of this needle, and the tip of every auto segmented needle is computed. The auto needle that
    offers the minimal tip axial distance is considered as corresponding needle

    :return: array of tuple of corresponding needles
    """
    # productive
    profprint()
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
    nbNode = modelNodes.GetNumberOfItems()
    result = []
    found = []
    # print nbNode
    for nthNode in range(nbNode):
      node = slicer.mrmlScene.GetNthNodeByClass(nthNode, 'vtkMRMLModelNode')
      if node.GetID() not in found and node.GetAttribute('type') != 'Validation':
        dist = []
        polydata = node.GetPolyData()
        if polydata != None:
          bounds = polydata.GetBounds()
          for nthNode2 in range(nbNode):
            node2 = slicer.mrmlScene.GetNthNodeByClass(nthNode2, 'vtkMRMLModelNode')
            if node2.GetID() not in found and node2.GetAttribute('type') == 'Validation':
              polydata2 = node2.GetPolyData()
              if polydata2 != None and polydata2.GetNumberOfPoints() > 100 and polydata.GetNumberOfPoints() > 100:

                axialDistance = self.distTip(int(node.GetID().strip('vtkMRMLModelNode')) , int(node2.GetID().strip('vtkMRMLModelNode')))
                
                dist.append([axialDistance, node2.GetID()])
                # print axialDistance
                
          if dist != []:
            match = [min(dist)[0], min(dist)[1], node.GetID()]
            result.append(match)
            found.append(min(dist)[1])
            found.append(node.GetID()) 
            node.GetDisplayNode().SetSliceIntersectionVisibility(1)
    # print result
    return result
  
  def setAllNeedleTubesAsValidationNeedles(self):
    """
    This is used for testing, R&D. It sets the needles to validation type.
    E.g. you load vtk needle models and want to use them as validation needles...
    """
    # #test #research #button
    profprint()
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
    nbNode = modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
      node = slicer.mrmlScene.GetNthNodeByClass(nthNode, 'vtkMRMLModelNode')
      if node.GetID() and node.GetAttribute('type') != 'Validation':
        node.SetAttribute('type', 'Validation')
        displayNode = node.GetDisplayNode()
        colorVar = random.randrange(50, 100, 1)  # ??? /(100.)
        nth = int(colorVar) % 64
        displayNode.SetColor(self.color[int(nth)][0], self.color[int(nth)][1], self.color[int(nth)][2])
        displayNode.SetSliceIntersectionVisibility(True)
        displayNode.SetSliceIntersectionThickness(2)
    
  def distance(self, pt1, pt2):
    """3D distance between two points

    :param pt1: point 1 [x,y,z]
    :param pt2: point 2 [x,y,z
    :return: Euclidian's distance
    """
    # productive #frequent
    if frequent: profprint()
    d = ((float(pt1[0]) - float(pt2[0])) ** 2 + (float(pt1[1]) - float(pt2[1])) ** 2 + (float(pt1[2]) - float(pt2[2])) ** 2) ** 0.5
    return d

  def addManualTip(self, A):
    """Add fiducial node to the scene (called by processEventAddManualTips). Used as starting point for needle segmentation

    :param A: RAS coordinates
    """
    # obsolete?
    profbox()
    self.fiducialNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    self.fiducialNode.Initialize(slicer.mrmlScene)
    self.fiducialNode.SetName('tip')
    self.fiducialNode.SetFiducialCoordinates(A)
    fd = self.fiducialNode.GetDisplayNode()
    fd.SetVisibility(1)
    fd.SetColor([0, 1, 0])

  def distanceTwoPoints(self, A, B):
    """3D distance between two points

    :param pt1: point 1 [x,y,z]
    :param pt2: point 2 [x,y,z
    :return: Euclidian's distance
    """
    # productive
    # used by addNeedleToScene
    if frequent: profprint()
    length = ((A[0] - B[0]) ** 2 + (A[1] - B[1]) ** 2 + (A[2] - B[2]) ** 2) ** 0.5
    return length
  
  def clipPolyData(self, node, value, visible=0):
    """ Function used to truncate needle models to evaluate the Hausdorff's distance.

    :param node: vtkMRMLModelNode
    :param value: axial slice where to cut the model
    :return: vtkPolyData of the cutted model
    """
    # productive
    profprint()
    # We clip with an implicit function. Here we use a plane positioned near
    # the center of the cow model and oriented at an arbitrary angle.
    plane = vtk.vtkPlane()
    plane.SetOrigin(0, 0, 0)
    plane.SetNormal(0, 0, 1)
    # vtkClipPolyData requires an implicit function to define what it is to
    # clip with. Any implicit function, including complex boolean combinations
    # can be used. Notice that we can specify the value of the implicit function
    # with the SetValue method.
    clipper = vtk.vtkClipPolyData()
    clipper.SetInputData(node.GetPolyData())
    clipper.SetClipFunction(plane)
    clipper.GenerateClipScalarsOn()
    clipper.GenerateClippedOutputOn()
    clipper.SetValue(value)
    clipper.Update()
    polyData = clipper.GetOutput()
    if 1 == 1:
        scene = slicer.mrmlScene
        model = slicer.vtkMRMLModelNode()
        model.SetScene(scene)
        model.SetAndObservePolyData(polyData)
        # ## Create display node
        modelDisplay = slicer.vtkMRMLModelDisplayNode()
        modelDisplay.SetScene(scene)
        scene.AddNode(modelDisplay)
        model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
        # ## Add to scene
        modelDisplay.SetInputPolyDataConnection(model.GetPolyDataConnection())
        scene.AddNode(model)
    if visible != 1:
        scene.RemoveNode(model)

    return polyData

  def setWL(self, dn, w, l):
    """
    Set window/level in mpr slice view
    """
    # productive #frequent #onDrag
    if frequent: profprint();
    dn.SetWindow(w)
    dn.SetLevel(l)

  def setColors255(self):
    """Set color map with colors encoded in RGB between 0 and 255
    """
    # productive
    profprint()
    self.color255 = [[0, 0, 0] for i in range(205)]
    self.color255[0] = [221, 108, 158]
    self.color255[1] = [128, 174, 128]
    self.color255[2] = [241, 214, 145]
    self.color255[3] = [177, 122, 101]
    self.color255[4] = [111, 184, 210]
    self.color255[5] = [216, 101, 79]
    self.color255[6] = [221, 130, 101]
    self.color255[7] = [144, 238, 144]
    self.color255[8] = [192, 104, 88]
    self.color255[9] = [220, 245, 20]
    self.color255[10] = [78, 63, 0]
    self.color255[11] = [255, 250, 220]
    self.color255[12] = [230, 220, 70]
    self.color255[13] = [200, 200, 235]
    self.color255[14] = [250, 250, 210]
    self.color255[15] = [244, 214, 49]
    self.color255[16] = [0, 151, 206]
    self.color255[17] = [183, 156, 220]
    self.color255[18] = [183, 214, 211]
    self.color255[19] = [152, 189, 207]
    self.color255[20] = [178, 212, 242]
    self.color255[21] = [68, 172, 100]
    self.color255[22] = [111, 197, 131]
    self.color255[23] = [85, 188, 255]
    self.color255[24] = [0, 145, 30]
    self.color255[25] = [214, 230, 130]
    self.color255[26] = [218, 255, 255]
    self.color255[27] = [170, 250, 250]
    self.color255[28] = [140, 224, 228]
    self.color255[29] = [188, 65, 28]
    self.color255[30] = [216, 191, 216]
    self.color255[31] = [145, 60, 66]
    self.color255[32] = [150, 98, 83]
    self.color255[33] = [250, 250, 225]
    self.color255[34] = [200, 200, 215]
    self.color255[35] = [68, 131, 98]
    self.color255[36] = [83, 146, 164]
    self.color255[37] = [162, 115, 105]
    self.color255[38] = [141, 93, 137]
    self.color255[39] = [182, 166, 110]
    self.color255[40] = [188, 135, 166]
    self.color255[41] = [154, 150, 201]
    self.color255[42] = [177, 140, 190]
    self.color255[43] = [30, 111, 85]
    self.color255[44] = [210, 157, 166]
    self.color255[45] = [48, 129, 126]
    self.color255[46] = [98, 153, 112]
    self.color255[47] = [69, 110, 53]
    self.color255[48] = [166, 113, 137]
    self.color255[49] = [122, 101, 38]
    self.color255[50] = [253, 135, 192]
    self.color255[51] = [145, 92, 109]
    self.color255[52] = [46, 101, 131]
    self.color255[53] = [0, 108, 112]
    self.color255[54] = [127, 150, 88]
    self.color255[55] = [159, 116, 163]
    self.color255[56] = [125, 102, 154]
    self.color255[57] = [106, 174, 155]
    self.color255[58] = [154, 146, 83]
    self.color255[59] = [126, 126, 55]
    self.color255[60] = [201, 160, 133]
    self.color255[61] = [78, 152, 141]
    self.color255[62] = [174, 140, 103]
    self.color255[63] = [139, 126, 177]
    self.color255[64] = [148, 120, 72]
    self.color255[65] = [186, 135, 135]
    self.color255[66] = [99, 106, 24]
    self.color255[67] = [156, 171, 108]
    self.color255[68] = [64, 123, 147]
    self.color255[69] = [138, 95, 74]
    self.color255[70] = [97, 113, 158]
    self.color255[71] = [126, 161, 197]
    self.color255[72] = [194, 195, 164]
    self.color255[73] = [88, 106, 215]
    self.color255[74] = [82, 174, 128]
    self.color255[75] = [57, 157, 110]
    self.color255[76] = [60, 143, 83]
    self.color255[77] = [92, 162, 109]
    self.color255[78] = [255, 244, 209]
    self.color255[79] = [201, 121, 77]
    self.color255[80] = [70, 163, 117]
    self.color255[81] = [188, 91, 95]
    self.color255[82] = [166, 84, 94]
    self.color255[83] = [182, 105, 107]
    self.color255[84] = [229, 147, 118]
    self.color255[85] = [174, 122, 90]
    self.color255[86] = [201, 112, 73]
    self.color255[87] = [194, 142, 0]
    self.color255[88] = [241, 213, 144]
    self.color255[89] = [203, 179, 77]
    self.color255[90] = [229, 204, 109]
    self.color255[91] = [255, 243, 152]
    self.color255[92] = [209, 185, 85]
    self.color255[93] = [248, 223, 131]
    self.color255[94] = [255, 230, 138]
    self.color255[95] = [196, 172, 68]
    self.color255[96] = [255, 255, 167]
    self.color255[97] = [255, 250, 160]
    self.color255[98] = [255, 237, 145]
    self.color255[99] = [242, 217, 123]
    self.color255[100] = [222, 198, 101]
    self.color255[101] = [213, 124, 109]
    self.color255[102] = [184, 105, 108]
    self.color255[103] = [150, 208, 243]
    self.color255[104] = [62, 162, 114]
    self.color255[105] = [242, 206, 142]
    self.color255[106] = [250, 210, 139]
    self.color255[107] = [255, 255, 207]
    self.color255[108] = [182, 228, 255]
    self.color255[109] = [175, 216, 244]
    self.color255[110] = [197, 165, 145]
    self.color255[111] = [172, 138, 115]
    self.color255[112] = [202, 164, 140]
    self.color255[113] = [224, 186, 162]
    self.color255[114] = [255, 245, 217]
    self.color255[115] = [206, 110, 84]
    self.color255[116] = [210, 115, 89]
    self.color255[117] = [203, 108, 81]
    self.color255[118] = [233, 138, 112]
    self.color255[119] = [195, 100, 73]
    self.color255[120] = [181, 85, 57]
    self.color255[121] = [152, 55, 13]
    self.color255[122] = [159, 63, 27]
    self.color255[123] = [166, 70, 38]
    self.color255[124] = [218, 123, 97]
    self.color255[125] = [225, 130, 104]
    self.color255[126] = [224, 97, 76]
    self.color255[127] = [184, 122, 154]
    self.color255[128] = [211, 171, 143]
    self.color255[129] = [47, 150, 103]
    self.color255[130] = [173, 121, 88]
    self.color255[131] = [188, 95, 76]
    self.color255[132] = [255, 239, 172]
    self.color255[133] = [226, 202, 134]
    self.color255[134] = [253, 232, 158]
    self.color255[135] = [244, 217, 154]
    self.color255[136] = [205, 179, 108]
    self.color255[137] = [186, 124, 161]
    self.color255[138] = [255, 255, 220]
    self.color255[139] = [234, 234, 194]
    self.color255[140] = [204, 142, 178]
    self.color255[141] = [180, 119, 153]
    self.color255[142] = [216, 132, 105]
    self.color255[143] = [255, 253, 229]
    self.color255[144] = [205, 167, 142]
    self.color255[145] = [204, 168, 143]
    self.color255[146] = [255, 224, 199]
    self.color255[147] = [139, 150, 98]
    self.color255[148] = [249, 180, 111]
    self.color255[149] = [157, 108, 162]
    self.color255[150] = [203, 136, 116]
    self.color255[151] = [185, 102, 83]
    self.color255[152] = [247, 182, 164]
    self.color255[153] = [222, 154, 132]
    self.color255[154] = [124, 186, 223]
    self.color255[155] = [249, 186, 150]
    self.color255[156] = [244, 170, 147]
    self.color255[157] = [255, 181, 158]
    self.color255[158] = [255, 190, 165]
    self.color255[159] = [227, 153, 130]
    self.color255[160] = [213, 141, 113]
    self.color255[161] = [193, 123, 103]
    self.color255[162] = [216, 146, 127]
    self.color255[163] = [230, 158, 140]
    self.color255[164] = [245, 172, 147]
    self.color255[165] = [241, 172, 151]
    self.color255[166] = [177, 124, 92]
    self.color255[167] = [171, 85, 68]
    self.color255[168] = [217, 198, 131]
    self.color255[169] = [212, 188, 102]
    self.color255[170] = [185, 135, 134]
    self.color255[171] = [198, 175, 125]
    self.color255[172] = [194, 98, 79]
    self.color255[173] = [255, 238, 170]
    self.color255[174] = [206, 111, 93]
    self.color255[175] = [216, 186, 0]
    self.color255[176] = [255, 226, 77]
    self.color255[177] = [255, 243, 106]
    self.color255[178] = [255, 234, 92]
    self.color255[179] = [240, 210, 35]
    self.color255[180] = [224, 194, 0]
    self.color255[181] = [213, 99, 79]
    self.color255[182] = [217, 102, 81]
    self.color255[183] = [0, 147, 202]
    self.color255[184] = [0, 122, 171]
    self.color255[185] = [186, 77, 64]
    self.color255[186] = [240, 255, 30]
    self.color255[187] = [185, 232, 61]
    self.color255[188] = [0, 226, 255]
    self.color255[189] = [251, 159, 255]
    self.color255[190] = [230, 169, 29]
    self.color255[191] = [0, 194, 113]
    self.color255[192] = [104, 160, 249]
    self.color255[193] = [221, 108, 158]
    self.color255[194] = [137, 142, 0]
    self.color255[195] = [230, 70, 0]
    self.color255[196] = [0, 147, 0]
    self.color255[197] = [0, 147, 248]
    self.color255[198] = [231, 0, 206]
    self.color255[199] = [129, 78, 0]
    self.color255[200] = [0, 116, 0]
    self.color255[201] = [0, 0, 255]
    self.color255[202] = [157, 0, 0]
    self.color255[203] = [100, 100, 130]
    self.color255[204] = [205, 205, 100]
    
    return self.color255

  def setColors(self):
    """Sets color map with colors encoded in RGB between 0 and 1
    """
    # productive
    profprint()
    self.color = [[0, 0, 0] for i in range(205)]
    self.color255 = self.setColors255()
    for i in range(205):
      for j in range(3):
        self.color[i][j] = self.color255[i][j] / float(255)

    return self.color

  def setHolesCoordinates(self):
    """Coordinates of the 63 holes in the obturator
    """
    # productive
    profprint()
    self.p = [[0 for j in range(63)] for j in range(3)]
    self.p[0][0] = 35
    self.p[1][0] = 34
    self.p[0][1] = 25
    self.p[1][1] = 36.679
    self.p[0][2] = 17.679
    self.p[1][2] = 44
    self.p[0][3] = 15
    self.p[1][3] = 54
    self.p[0][4] = 17.679
    self.p[1][4] = 64
    self.p[0][5] = 25
    self.p[1][5] = 71.321
    self.p[0][6] = 35
    self.p[1][6] = 74
    self.p[0][7] = 45
    self.p[1][7] = 71.321
    self.p[0][8] = 52.321
    self.p[1][8] = 64
    self.p[0][9] = 55
    self.p[1][9] = 54
    self.p[0][10] = 52.321
    self.p[1][10] = 44
    self.p[0][11] = 45
    self.p[1][11] = 36.679
    self.p[0][12] = 29.791
    self.p[1][12] = 24.456
    self.p[0][13] = 20
    self.p[1][13] = 28.019
    self.p[0][14] = 12.019
    self.p[1][14] = 34.716
    self.p[0][15] = 6.809
    self.p[1][15] = 43.739
    self.p[0][16] = 5
    self.p[1][16] = 54
    self.p[0][17] = 6.809
    self.p[1][17] = 64.261
    self.p[0][18] = 12.019
    self.p[1][18] = 73.284
    self.p[0][19] = 20
    self.p[1][19] = 79.981
    self.p[0][20] = 29.791
    self.p[1][20] = 83.544
    self.p[0][21] = 40.209
    self.p[1][21] = 83.544
    self.p[0][22] = 50
    self.p[1][22] = 79.981
    self.p[0][23] = 57.981
    self.p[1][23] = 73.284
    self.p[0][24] = 63.191
    self.p[1][24] = 64.262
    self.p[0][25] = 65
    self.p[1][25] = 54
    self.p[0][26] = 63.191
    self.p[1][26] = 43.739
    self.p[0][27] = 57.981
    self.p[1][27] = 34.716
    self.p[0][28] = 50
    self.p[1][28] = 28.019
    self.p[0][29] = 40.209
    self.p[1][29] = 24.456
    self.p[0][30] = 35
    self.p[1][30] = 14
    self.p[0][31] = 24.647
    self.p[1][31] = 15.363
    self.p[0][32] = 15
    self.p[1][32] = 19.359
    self.p[0][33] = 15
    self.p[1][33] = 88.641
    self.p[0][34] = 24.647
    self.p[1][34] = 92.637
    self.p[0][35] = 35
    self.p[1][35] = 94
    self.p[0][36] = 45.353
    self.p[1][36] = 92.637
    self.p[0][37] = 55
    self.p[1][37] = 88.641
    self.p[0][38] = 55
    self.p[1][38] = 19.359
    self.p[0][39] = 45.353
    self.p[1][39] = 15.363
    self.p[0][40] = 30.642
    self.p[1][40] = 4.19
    self.p[0][41] = 22.059
    self.p[1][41] = 5.704
    self.p[0][42] = 22.059
    self.p[1][42] = 102.296
    self.p[0][43] = 30.642
    self.p[1][43] = 103.81
    self.p[0][44] = 39.358
    self.p[1][44] = 103.81
    self.p[0][45] = 47.941
    self.p[1][45] = 102.296
    self.p[0][46] = 47.941
    self.p[1][46] = 5.704
    self.p[0][47] = 39.358
    self.p[1][47] = 4.19
    self.p[0][48] = 29.7
    self.p[1][48] = 44.82
    self.p[0][49] = 24.4
    self.p[1][49] = 54
    self.p[0][50] = 29.7
    self.p[1][50] = 63.18
    self.p[0][51] = 40.3
    self.p[1][51] = 63.18
    self.p[0][52] = 45.6
    self.p[1][52] = 54
    self.p[0][53] = 40.3
    self.p[1][53] = 44.82
    self.p[0][54] = 35
    self.p[1][54] = 54
    self.p[0][55] = 9
    self.p[1][55] = 12
    self.p[0][56] = 5
    self.p[1][56] = 18
    self.p[0][57] = 5
    self.p[1][57] = 90
    self.p[0][58] = 9
    self.p[1][58] = 96
    self.p[0][59] = 61
    self.p[1][59] = 96
    self.p[0][60] = 65
    self.p[1][60] = 90
    self.p[0][61] = 65
    self.p[1][61] = 18
    self.p[0][62] = 61
    self.p[1][62] = 12

    return self.p

  def setLabels(self):
    """
    Set the list of labels corresponding of the 63 holes of the obturator
    """
    # productive
    profprint()
    self.option = {0:'Ba',
       1:'Bb',
       2:'Bc',
       3:'Bd',
       4:'Be',
       5:'Bf',
       6:'Bg',
       7:'Bh',
       8:'Bi',
       9:'Bj',
       10:'Bk',
       11:'Bl',
       12:'Ca',
       13:'Cb',
       14:'Cc',
       15:'Cd',
       16:'Ce',
       17:'Cf',
       18:'Cg',
       19:'Ch',
       20:'Ci',
       21:'Cj',
       22:'Ck',
       23:'Cl',
       24:'Cm',
       25:'Cn',
       26:'Co',
       27:'Cp',
       28:'Cq',
       29:'Cr',
       30:'Da',
       31:'Db',
       32:'Dc',
       33:'Dd',
       34:'De',
       35:'Df',
       36:'Dg',
       37:'Dh',
       38:'Di',
       39:'Dj',
       40:'Ea',
       41:'Eb',
       42:'Ec',
       43:'Ed',
       44:'Ee',
       45:'Ef',
       46:'Eg',
       47:'Eh',
       48:'Aa',
       49:'Ab',
       50:'Ac',
       51:'Ad',
       52:'Ae',
       53:'Af',
       54:'Iu',
       55:'Fa',
       56:'Fb',
       57:'Fc',
       58:'Fd',
       59:'Fe',
       60:'Ff',
       61:'Fg',
       62:'Fh',
       63:'--'}

    return self.option
  
  def setParameterNode(self, parameterNode):
    """Set Parameter Node (to save parameters from one step to the other)
    ??? used?
    """
    # framework
    profbox()
    self.parameterNode = parameterNode

  def parameterNode(self):
    """Returns parameter node
    ??? used?
    """
    # framework
    profbox()
    return self.parameterNode

  def getBoldFont(self):
    """Get a Qt bold font
    ??? Used?
    """
    # obsolete?
    profbox()
    boldFont = qt.QFont("Sans Serif", 12, qt.QFont.Bold)
    return boldFont 
  
  def saveParameters (self , filePath):
    """
    save the current needle detection parameters to file
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    config = ConfigParser.RawConfigParser()
    config.add_section('NeedleFinder Parameters')
    config.add_section('BooleanSection')
    config.add_section('IntegerSection')

    config.set('BooleanSection', 'autoCorrectTip', widget.autoCorrectTip.isChecked())
    config.set('BooleanSection', 'invertedContrast', widget.invertedContrast.isChecked())
    config.set('BooleanSection', 'gradient', widget.gradient.isChecked())
    config.set('BooleanSection', 'filterControlPoints', widget.filterControlPoints.isChecked())
    config.set('BooleanSection', 'drawFiducialPoints', widget.drawFiducialPoints.isChecked())
    config.set('BooleanSection', 'autoStopTip', widget.autoStopTip.isChecked())
    config.set('BooleanSection', 'extendNeedle', widget.extendNeedle.isChecked())
    config.set('BooleanSection', 'maxLength', widget.maxLength.isChecked())
    config.set('BooleanSection', 'gaussianAttenuationButton', widget.gaussianAttenuationButton.isChecked())

    config.set('IntegerSection', 'realNeedleLength', widget.realNeedleLength.value)
    config.set('IntegerSection', 'sigmaValue', widget.sigmaValue.value)
    config.set('IntegerSection', 'gradientPonderation', widget.gradientPonderation.value)
    config.set('IntegerSection', 'exponent', widget.exponent.value)
    config.set('IntegerSection', 'distanceMax', widget.radiusMax.value)
    config.set('IntegerSection', 'nbRotatingIterations', widget.nbRotatingIterations.value)
    config.set('IntegerSection', 'numberOfPointsPerNeedle', widget.numberOfPointsPerNeedle.value)
    config.set('IntegerSection', 'lenghtNeedleParameter', widget.lenghtNeedleParameter.value)
    config.set('IntegerSection', 'radiusNeedleParameter', widget.radiusNeedleParameter.value)
    config.set('IntegerSection', 'algoVersParameter', widget.algoVersParameter.value)

    # Writing our configuration file to 'example.cfg'
    with open(filePath, 'wb') as configfile:
        config.write(configfile)

  def loadParameters (self, filePath):
    """
    load the parameters from parameter text file
    """
    # productive #onButton
    profprint()
    widget = slicer.modules.NeedleFinderWidget
    config = ConfigParser.RawConfigParser()
    config.read(filePath)

    autoCorrectTip = config.getboolean('BooleanSection', 'autoCorrectTip')
    invertedContrast = config.getboolean('BooleanSection', 'invertedContrast')
    gradient = config.getboolean('BooleanSection', 'gradient')
    filterControlPoints = config.getboolean('BooleanSection', 'filterControlPoints')
    drawFiducialPoints = config.getboolean('BooleanSection', 'drawFiducialPoints')
    autoStopTip = config.getboolean('BooleanSection', 'autoStopTip')
    extendNeedle = config.getboolean('BooleanSection', 'extendNeedle')
    maxLength = config.getboolean('BooleanSection', 'maxLength')
    gaussianAttenuationButton = config.getboolean('BooleanSection', 'gaussianAttenuationButton')

    realNeedleLength = config.getint('IntegerSection', 'realNeedleLength')
    sigmaValue = config.getint('IntegerSection', 'sigmaValue')
    gradientPonderation = config.getint('IntegerSection', 'gradientPonderation')
    exponent = config.getint('IntegerSection', 'exponent')
    try:
      radiusMax = config.getint('IntegerSection', 'distanceMax') # try deprecated parameter name (old parameter files)
    except:
      radiusMax = config.getint('IntegerSection', 'radiusMax')
    nbRotatingIterations = config.getint('IntegerSection', 'nbRotatingIterations')
    numberOfPointsPerNeedle = config.getint('IntegerSection', 'numberOfPointsPerNeedle')
    lenghtNeedleParameter = config.getint('IntegerSection', 'lenghtNeedleParameter')
    radiusNeedleParameter = config.getint('IntegerSection', 'radiusNeedleParameter')
    algoVersParameter = config.getint('IntegerSection', 'algoVersParameter')
    
    widget.autoCorrectTip.checked = autoCorrectTip
    widget.invertedContrast.checked = invertedContrast
    widget.gradient.checked = gradient 
    widget.filterControlPoints.checked = filterControlPoints
    widget.drawFiducialPoints.checked = drawFiducialPoints
    widget.autoStopTip.checked = autoStopTip
    widget.extendNeedle.checked = extendNeedle
    widget.maxLength.checked = maxLength
    widget.gaussianAttenuationButton.checked = gaussianAttenuationButton

    widget.realNeedleLength.value = realNeedleLength
    widget.sigmaValue.value = sigmaValue
    widget.gradientPonderation.value = gradientPonderation
    widget.exponent.value = exponent
    widget.radiusMax.value = radiusMax
    widget.nbRotatingIterations.value = nbRotatingIterations
    widget.numberOfPointsPerNeedle.value = numberOfPointsPerNeedle
    widget.lenghtNeedleParameter.value = lenghtNeedleParameter
    widget.radiusNeedleParameter.value = radiusNeedleParameter
    widget.algoVersParameter.value = algoVersParameter
    print "#############"
    print "algoVers: ", algoVersParameter
    print "Parameters successfully loaded!"
    
"""

########################################################################################################################
TESTS
########################################################################################################################

"""

class NeedleFinderTest(unittest.TestCase):
  """
  This is the test case for your scripted module.
  """

  def getName(self):
    """
    return class name
    """
    return self.__class__.__name__

  def delayDisplay(self, message, msec=1000):
    """ Test:
    This utility method displays a small dialog and waits.
    This does two things: 1) it lets the event loop catch up
    to the state of the test so that rendering and widget updates
    have all taken place before the test continues and 2) it
    shows the user/developer/tester the state of the test
    so that we'll know when it breaks.
    """
    # test
    profprint()
    print(message)
    self.info = qt.QDialog()
    self.infoLayout = qt.QVBoxLayout()
    self.info.setLayout(self.infoLayout)
    self.label = qt.QLabel(message, self.info)
    self.infoLayout.addWidget(self.label)
    qt.QTimer.singleShot(msec, self.info.close)
    self.info.exec_()

  def setUp(self):
    """ Test:
    Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    # test
    profprint()
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """ Test:
    Run as few or as many tests as needed here.
    """
    # test #framework #productive
    profprint()
    
    self.setUp()
    self.test_NeedleFinder1()

  def test_NeedleFinder1(self):
    """
    Unit test
    """
    # test #framework
    profprint()
    """
    Ideally you should have several levels of tests.  At the lowest level
    tests sould exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url, name, loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        print('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        print('Loading %s...\n' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading\n')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = NeedleFinderLogic()
    self.assertTrue(logic.hasImageData(volumeNode))
    self.delayDisplay('Test passed!')
