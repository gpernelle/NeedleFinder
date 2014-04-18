from __future__ import division
from __main__ import qt, ctk, slicer


from NFStep import *
from Helper import *
from EditorLib import *
import math,time, functools, operator
import EditorLib
import string
import numpy
import thread
import random
import copy
import operator
import csv
import numpy as np

class NFNeedleSegmentationStep( NFStep ) :
  '''
  Tools to manually and automatically segment catheters
    - Can be used in MR images or CT images (a checkbox to check in the parameter settings )
    - Can track from the tip or from any point (work in progress)
    - Can extend the catheter to a desired value (default: 240mm)

  TODO: 
    - export function
    - possibility to reset the obturator needles (cf. validation/segmentation needles)
    - change initialisation of control point lists to something cleaner
    - write a segmentation report?


  '''

  def __init__( self, stepid ):
    self.skip = 1
    self.initialize( stepid )
    self.setName( '7. Needle Segmentation' )
    self.setDescription( 'Click on the needle tips to segment the needles' )
    self.__parent = super( NFNeedleSegmentationStep, self )
    self.analysisGroupBox   = None
    self.buttonsGroupBox    = None
    self.round              = 1
    self.row                = 0
    self.validationNeedleNumber = 0
    self.fiducialNode       = None
    self.axialSegmentationLimit = None
    self.stepNeedle         = 0
    self.tableValueCtrPt    = [[[999,999,999] for i in range(100)] for j in range(100)]
    self.obtuNeedleValueCtrPt = [[[999,999,999] for i in range(10)] for j in range(10)]
    self.obtuNeedlePt = [[[999,999,999] for i in range(10)] for j in range(10)]
    self.ptNumber           = 0
    self.table              = None
    self.view               = None
    self.previousValues     = [[0,0,0]]
    self.interactorObserverTags = []    
    self.styleObserverTags  = []
    # initialisation of parameters (colors, holes coordinates. cf. NFStep.py)
    self.option             = self.setLabels()
    self.color              = self.setColors()
    self.color255           = self.setColors255()
    self.p                  = self.setHolesCoordinates()
    self.t0                 = 0
    self.obtuNeedle         = 0

    # state management for compressing events
    self.resumeModelRequested = False
    self.updateRecentActivityRequested = False
    
  def createUserInterface( self ):
    '''
    '''
    self.skip = 0
    pNode = self.parameterNode()
    self.__layout = self.__parent.createUserInterface()

    #-----------------------------------------------------------------------------
    #Report Frame
    self.__reportFrame = ctk.ctkCollapsibleButton()
    self.__reportFrame.text = "Segmentation Report"
    self.__reportFrame.collapsed = 1
    reportFrame = qt.QFormLayout(self.__reportFrame)

    # segmentation report
    self.analysisGroupBox = qt.QGroupBox()
    self.analysisGroupBox.setFixedHeight(330)
    self.analysisGroupBox.setTitle( 'Segmentation Report' )
    reportFrame.addRow( self.analysisGroupBox )
    self.analysisGroupBoxLayout = qt.QFormLayout( self.analysisGroupBox )

    #-----------------------------------------------------------------------------

    #Segmentation Frame
    self.__segmentationFrame = ctk.ctkCollapsibleButton()
    self.__segmentationFrame.text = "Segmentation"
    self.__segmentationFrame.collapsed = 1
    segmentationFrame = qt.QFormLayout(self.__segmentationFrame)

    # give needle tips
    self.fiducialButton = qt.QPushButton('Start Giving Needle Tips')
    self.fiducialButton.checkable = True
    segmentationFrame.addRow(self.fiducialButton)
    self.fiducialButton.connect('toggled(bool)', self.onRunButtonToggled)

    # Obturator needle tips
    self.fiducialObturatorButton = qt.QPushButton('Start Giving Obturator Needle Tips')
    self.fiducialObturatorButton.checkable = True
    segmentationFrame.addRow(self.fiducialObturatorButton)
    self.fiducialObturatorButton.connect('toggled(bool)', self.onRunObturatorButtonToggled)

    # #Segment Needle Button 
    # self.needleButton = qt.QPushButton('Segment Needles')
    # segmentationFrame.addRow(self.needleButton)
    # self.needleButton.connect('clicked()', self.needleSegmentation)
    # self.needleButton.setEnabled(0)

    #Segment Needle Button 
    # self.needleButton2 = qt.QPushButton('Segment/Update Needles - Python')
    # segmentationFrame.addRow(self.needleButton2)
    # self.needleButton2.connect('clicked()', self.needleDetection)

    #New insertion - create new round of needles with different colors
    self.newInsertionButton = qt.QPushButton('New Insertion Needle')
    segmentationFrame.addRow(self.newInsertionButton)
    self.newInsertionButton.connect('clicked()', self.newInsertionNeedle)

    #Delete Needles Button 
    self.deleteNeedleButton = qt.QPushButton('Delete Segmented Needles')
    segmentationFrame.addRow(self.deleteNeedleButton)
    self.deleteNeedleButton.connect('clicked()', self.deleteSegmentedNeedle)

    #Reset Needle Detection Button 
    self.resetDetectionButton = qt.QPushButton('Reset Needle Detection')
    segmentationFrame.addRow(self.resetDetectionButton)
    self.resetDetectionButton.connect('clicked()', self.resetNeedleDetection)

    #Define template
    self.templateSliceButton =  qt.QPushButton('Select Current Axial Slice as seg. limit (current: None)')
    segmentationFrame.addRow(self.templateSliceButton)
    self.templateSliceButton.connect('clicked()', self.selectCurrentAxialSlice)

    
    self.updateWidgetFromParameters(self.parameterNode())
      
  	#Validation Frame
    self.__validationFrame = ctk.ctkCollapsibleButton()
    self.__validationFrame.text = "Validation"
    self.__validationFrame.collapsed = 1
    validationFrame = qt.QFormLayout(self.__validationFrame)

    self.validationNeedleButton = qt.QPushButton('New Validation Needle: (0)->(1)')
    self.validationNeedleButton.toolTip =   "By clicking on this button, you will increment the number of the needle"
    self.validationNeedleButton.toolTip +=   "that you want to manually segment. Thus, the points you will add will be used to draw a new needle.<br/>"
    self.validationNeedleButton.toolTip +=   "<b>Warning:<b> You can/'t add any more points to the current needle after clicking here"
    validationFrame.addRow(self.validationNeedleButton)
    self.validationNeedleButton.connect('clicked()', self.validationNeedle)

    self.startGivingControlPointsButton = qt.QPushButton('Start Giving Control Points')
    self.startGivingControlPointsButton.checkable = True
    validationFrame.addRow(self.startGivingControlPointsButton)
    self.startGivingControlPointsButton.connect('toggled(bool)', self.onNeedleValidationButtonToggled)

    self.drawValidationNeedlesButton = qt.QPushButton('(Re)Draw Needles 3D Models')
    self.drawValidationNeedlesButton.toolTip = "Redraw every manually segmented needles. This is usefull for example if you moved a control point, or after you added a new needle"
    validationFrame.addRow(self.drawValidationNeedlesButton)
    self.drawValidationNeedlesButton.connect('clicked()', self.drawValidationNeedles)

    self.startValidationButton = qt.QPushButton('Start Evaluation')
    self.startValidationButton.toolTip = "Launch tracking algo. from the tip of the manually segmented needles"
    validationFrame.addRow(self.startValidationButton)
    self.startValidationButton.connect('clicked()', self.startValidation)

    #Reset Needle Validation Button 
    self.resetDetectionButton = qt.QPushButton('Reset Needles from Manual Segmention')
    validationFrame.addRow(self.resetDetectionButton)
    self.resetDetectionButton.connect('clicked()', self.resetNeedleValidation)

    self.editNeedleTxtBox = qt.QSpinBox()
    self.editNeedleTxtBox.connect("valueChanged(int)",self.changeValue)
    editLabel= qt.QLabel('Choose Needle for Ctrl Pt scrolling:')
    validationFrame.addRow(editLabel, self.editNeedleTxtBox)

    self.scrollPointButton = qt.QPushButton('Scroll Ctrl Pt for Needle '+str(self.editNeedleTxtBox.value))
    validationFrame.addRow(self.scrollPointButton)
    self.scrollPointButton.connect('clicked()', self.scrollPoint)

    #Filter Needles Button
    self.__filterFrame = ctk.ctkCollapsibleButton()
    self.__filterFrame.text = "Filter Needles"
    self.__filterFrame.collapsed = 1
    filterFrame = qt.QFormLayout(self.__filterFrame)
    
    # Filter spin box
    # self.filterValueButton = qt.QSpinBox()
    # self.filterValueButton.setMaximum(500)
    # fLabel = qt.QLabel("Max Deviation Value: ")
    
    # self.removeDuplicates = qt.QCheckBox('Remove duplicates by segmenting')
    # self.removeDuplicates.setChecked(1)
    # self.removeDuplicatesButton = qt.QPushButton('Remove duplicates')
    # self.removeDuplicatesButton.connect('clicked()', self.positionFilteringNeedles)
    
    # filterNeedlesButton = qt.QPushButton('Filter Needles')
    # filterNeedlesButton.connect('clicked()', self.angleFilteringNeedles)
    
    # filterFrame.addRow(self.removeDuplicates)
    # filterFrame.addRow(self.removeDuplicatesButton)
    
    # filterFrame.addRow(fLabel,self.filterValueButton)
    # filterFrame.addRow(filterNeedlesButton)
    
    self.displayFiducialButton = qt.QPushButton('Display Labels On Needles')
    self.displayFiducialButton.connect('clicked()',self.displayFiducial)
    # self.displayRadPlannedButton = qt.QPushButton('Hide Radiation On Planned Needles')
    # self.displayRadPlannedButton.checkable = True
    # self.displayRadPlannedButton.connect('clicked()',self.displayRadPlanned)
    # self.displayRadSegmentedButton = qt.QPushButton('Hide Radiation On Segmented Needles')
    # self.displayRadSegmentedButton.checkable = True
    # self.displayRadSegmentedButton.connect('clicked()',self.displayRadSegmented)
    self.displayContourButton = qt.QPushButton('Draw Isosurfaces')
    self.displayContourButton.checkable = False
    self.displayContourButton.connect('clicked()',self.drawIsoSurfaces)
    self.hideContourButton = qt.QPushButton('Hide Isosurfaces')
    self.hideContourButton.checkable = True
    self.hideContourButton.connect('clicked()',self.hideIsoSurfaces)
    self.hideContourButton.setEnabled(0)
    # self.analysisReportButton = qt.QPushButton('Print Analysis')
    # self.analysisReportButton.connect('clicked()',self.analyzeSegmentation)
    
    
    segmentationFrame.addRow(self.displayFiducialButton)
    # self.__layout.addRow(self.displayRadPlannedButton)
    # self.__layout.addRow(self.displayRadSegmentedButton)
    segmentationFrame.addRow(self.displayContourButton)
    segmentationFrame.addRow(self.hideContourButton)
    # self.__layout.addRow(self.analysisReportButton)
    

    # Bending parameters
    self.__bendingFrame = ctk.ctkCollapsibleButton()
    self.__bendingFrame.text = "Needle Detection Parameters"
    self.__bendingFrame.collapsed = 1
    bendingFrame = qt.QFormLayout(self.__bendingFrame)
    
    
    # Auto correct tip position?
    self.autoCorrectTip = qt.QCheckBox('Auto correct tip position?')
    bendingFrame.addRow(self.autoCorrectTip)
    self.autoCorrectTip.setChecked(1)

    # Look for needles in CT?
    self.invertedContrast = qt.QCheckBox('Search for bright needles (CT)?')
    bendingFrame.addRow(self.invertedContrast)
    # Compute gradient?
    self.gradient=qt.QCheckBox('Compute gradient?')
    self.gradient.setChecked(1)
    bendingFrame.addRow(self.gradient)

    # Filter ControlPoints?
    self.filterControlPoints=qt.QCheckBox('Filter Control Points?')
    self.filterControlPoints.setChecked(0)
    # bendingFrame.addRow(self.filterControlPoints)

    # Draw Fiducial Points?
    self.drawFiducialPoints=qt.QCheckBox('Draw Control Points?')
    self.drawFiducialPoints.setChecked(0)
    bendingFrame.addRow(self.drawFiducialPoints)

    # Auto find Tips: Tracking in +z and -z direction
    self.autoStopTip = qt.QCheckBox('Tracking in both directions')
    self.autoStopTip.setChecked(0)
    bendingFrame.addRow(self.autoStopTip)

    # Extend Needle to the wanted value
    self.extendNeedle = qt.QCheckBox('Extend Needle')
    self.extendNeedle.setChecked(0)
    bendingFrame.addRow(self.extendNeedle)

    # Real Needle Value (used to extend the needle)
    realNeedleLengthLabel = qt.QLabel('Real Needle Length (mm):')
    self.realNeedleLength = qt.QSpinBox()
    self.realNeedleLength.setMinimum(0.1)
    self.realNeedleLength.setMaximum(1500)
    self.realNeedleLength.setValue(240)
    bendingFrame.addRow(realNeedleLengthLabel,self.realNeedleLength)


    # Max Needle Length?
    self.maxLength=qt.QCheckBox('Max Needle Length?')
    self.maxLength.setChecked(1)
    bendingFrame.addRow(self.maxLength)

    # Add Gaussian Estimation?
    self.gaussianAttenuationButton = qt.QCheckBox('Add Gaussian Prob. Attenuation?')
    self.gaussianAttenuationButton.setChecked(1)
    bendingFrame.addRow(self.gaussianAttenuationButton)


    # nb points per line spin box
    ### previously 4 - try with 20
    self.sigmaValue = qt.QSpinBox()
    self.sigmaValue.setMinimum(0.1)
    self.sigmaValue.setMaximum(500)
    self.sigmaValue.setValue(20)
    sigmaValueLabel = qt.QLabel("Sigma Value (exp(-x^2/(2*(sigma/10)^2))): ")
    bendingFrame.addRow( sigmaValueLabel, self.sigmaValue)

    # nb points per line spin box
    self.gradientPonderation = qt.QSpinBox()
    self.gradientPonderation.setMinimum(0.01)
    self.gradientPonderation.setMaximum(500)
    self.gradientPonderation.setValue(5)
    gradientPonderationLabel = qt.QLabel("Neighborhood Ponderation: ")
    bendingFrame.addRow( gradientPonderationLabel, self.gradientPonderation)

    # center accuentuation
    ### previously 1, try with 2 ( avoids exiting catheter track)
    self.exponent = qt.QSpinBox()
    self.exponent.setMinimum(0.01)
    self.exponent.setMaximum(500)
    self.exponent.setValue(2)
    exponentLabel = qt.QLabel("Center Ponderation: ")
    bendingFrame.addRow( exponentLabel, self.exponent)

    # nb points per line spin box
    self.nbPointsPerLine = qt.QSpinBox()
    self.nbPointsPerLine.setMinimum(2)
    self.nbPointsPerLine.setMaximum(500)
    self.nbPointsPerLine.setValue(20)
    nbPointsPerLineLabel = qt.QLabel("Number of points per line: ")
    # bendingFrame.addRow( nbPointsPerLineLabel, self.nbPointsPerLine)

    # nb radius iteration spin box
    self.nbRadiusIterations = qt.QSpinBox()
    self.nbRadiusIterations.setMinimum(2)
    self.nbRadiusIterations.setMaximum(50)
    self.nbRadiusIterations.setValue(13)
    nbRadiusIterationsLabel = qt.QLabel("Number of distance iterations: ")
    # bendingFrame.addRow( nbRadiusIterationsLabel, self.nbRadiusIterations)
    
    # distance max spin box
    self.distanceMax = qt.QSpinBox()
    self.distanceMax.setMinimum(0)
    self.distanceMax.setMaximum(50)
    self.distanceMax.setValue(5)
    distanceMaxLabel = qt.QLabel("Radius of cone base (mm): ")
    bendingFrame.addRow( distanceMaxLabel, self.distanceMax)
    
    # nb rotating iterations spin box
    self.nbRotatingIterations = qt.QSpinBox()
    self.nbRotatingIterations.setMinimum(2)
    self.nbRotatingIterations.setMaximum(50)
    self.nbRotatingIterations.setValue(35)
    nbRotatingIterationsLabel = qt.QLabel("Number of rotating steps: ")
    bendingFrame.addRow( nbRotatingIterationsLabel, self.nbRotatingIterations)
    
    # nb heights per needle spin box
    self.numberOfPointsPerNeedle = qt.QSpinBox()
    self.numberOfPointsPerNeedle.setMinimum(1)
    self.numberOfPointsPerNeedle.setMaximum(50)
    self.numberOfPointsPerNeedle.setValue(6)
    numberOfPointsPerNeedleLabel = qt.QLabel("Number of Control Points: ")
    bendingFrame.addRow( numberOfPointsPerNeedleLabel, self.numberOfPointsPerNeedle)

    # nb heights per needle spin box
    self.stepsize = qt.QSpinBox()
    self.stepsize.setMinimum(1)
    self.stepsize.setMaximum(50)
    self.stepsize.setValue(5)
    stepsizeLabel = qt.QLabel("Stepsize: ")
    # bendingFrame.addRow( stepsizeLabel, self.stepsize)

    #lenghtNeedle
    self.lenghtNeedleParameter = qt.QSpinBox()
    self.lenghtNeedleParameter.setMinimum(1)
    self.lenghtNeedleParameter.setMaximum(1000)
    self.lenghtNeedleParameter.setValue(100)
    stepsizeLabel = qt.QLabel("Lenght of the needles (mm): ")
    bendingFrame.addRow( stepsizeLabel, self.lenghtNeedleParameter)

    #radius
    self.radiusNeedleParameter = qt.QSpinBox()
    self.radiusNeedleParameter.setMinimum(1)
    self.radiusNeedleParameter.setMaximum(200)
    self.radiusNeedleParameter.setValue(2)
    radiusLabel = qt.QLabel("Radius of the needles (mm): ")
    bendingFrame.addRow( radiusLabel, self.radiusNeedleParameter)
    
    self.__layout.addRow(self.__reportFrame)
    self.__layout.addRow(self.__segmentationFrame)
    self.__layout.addRow(self.__validationFrame)
    # self.__layout.addRow(self.__filterFrame)
    self.__layout.addRow(self.__bendingFrame)
    # reset module
    
    resetButton = qt.QPushButton( 'Reset Module' )
    resetButton.connect( 'clicked()', self.onResetButton )
    # self.__layout.addRow(resetButton)

    qt.QTimer.singleShot(0, self.killButton)
      
  def killButton(self):
    # hide useless button
    bl = slicer.util.findChildren(text='NeedleSegmentation')
    if len(bl):
      bl[0].hide()
  
  def onResetButton( self ):
    '''
    need to be fixed. Goal is to lead user to first step
    TODO: option to close scene and start over everything
    '''
    self.workflow().goBackward() # 6
    self.workflow().goBackward() # 5
    self.workflow().goBackward() # 4
    self.workflow().goBackward() # 3
    self.workflow().goBackward() # 2
    self.workflow().goBackward() # 1 
             
  def validate( self, desiredBranchId ):
    '''
    '''
    self.__parent.validate( desiredBranchId )
    self.__parent.validationSucceeded(desiredBranchId)

  def onExit(self, goingTo, transitionType):
    if goingTo.id() != 'NeedlePlanning' and goingTo.id() != 'NeedleSegmentation':
      return

    pNode = self.parameterNode()
   

    super(NFNeedleSegmentationStep, self).onExit(goingTo, transitionType)

  def onEntry(self,comingFrom,transitionType):
    '''
    Update GUI and visualization
    '''
    super(NFNeedleSegmentationStep, self).onEntry(comingFrom, transitionType)
    pNode = self.parameterNode()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()

    if pNode.GetParameter('skip') != '1' and volumeNode != None:
      self.updateWidgetFromParameters(pNode)
      Helper.SetBgFgVolumes(pNode.GetParameter('baselineVolumeID'),'')
      obturator = slicer.mrmlScene.GetNodeByID(pNode.GetParameter('obturatorID'))
      template = slicer.mrmlScene.GetNodeByID(pNode.GetParameter('templateID'))
      dObturator = obturator.GetDisplayNode()
      dObturator.SetVisibility(0)
      dTemplate = template.GetDisplayNode()
      dTemplate.SetVisibility(0)

    pNode.SetParameter('skip','0')  
    pNode.SetParameter('currentStep', self.stepid)
      
  def updateWidgetFromParameters(self, pNode):
  
    self.baselineVolume = slicer.mrmlScene.GetNodeByID(pNode.GetParameter('baselineVolumeID'))
    transformNodeID = pNode.GetParameter('followupTransformID')
    self.transform = slicer.mrmlScene.GetNodeByID(transformNodeID)
    
  #----------------------------------------------------------------------------------------------
  ''' Visualization functions '''
  #----------------------------------------------------------------------------------------------

  def drawIsoSurfaces( self ):
    '''
    Draw isosurfaces from models of the visible needles only
    '''
    self.hideContourButton.setEnabled(1)
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
       
    v= vtk.vtkAppendPolyData()
    canContinue = 0
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth")!=None and modelNode.GetDisplayVisibility()==1 :
        canContinue = 1
        v.AddInput(modelNode.GetPolyData())
       
    if canContinue ==1:
      modeller = vtk.vtkImplicitModeller()
      modeller.SetInput(v.GetOutput())
      modeller.SetSampleDimensions(60,60,60)
      modeller.SetCapping(0)
      modeller.AdjustBoundsOn()
      modeller.SetProcessModeToPerVoxel() 
      modeller.SetAdjustDistance(1)
      modeller.SetMaximumDistance(1.0)    
      
      contourFilter = vtk.vtkContourFilter()
      contourFilter.SetNumberOfContours(1)
      contourFilter.SetInputConnection(modeller.GetOutputPort())    
      contourFilter.ComputeNormalsOn()
      contourFilter.ComputeScalarsOn()
      contourFilter.UseScalarTreeOn()
      contourFilter.SetValue(1,10)
      # contourFilter.SetValue(2,13)
      # contourFilter.SetValue(3,15)
      # contourFilter.SetValue(4,20)
      # contourFilter.SetValue(5,25)
      isoSurface = contourFilter.GetOutput()

      self.AddContour(isoSurface)

  def hideIsoSurfaces(self):
    contourNode = None
    contourNode = slicer.util.getNode('Contours')
    if contourNode != None:
      contourNode.SetDisplayVisibility(abs(self.hideContourButton.isChecked()-1))
      contourNode.GetModelDisplayNode().SetSliceIntersectionVisibility(abs(self.hideContourButton.isChecked()-1))

  def displayNeedleID(self,ID):
    modelNode = slicer.util.getNode('vtkMRMLModelNode'+str(ID))
    displayNode = modelNode.GetModelDisplayNode()
    nVisibility = displayNode.GetVisibility()
    # print nVisibility
    if nVisibility:
      displayNode.SliceIntersectionVisibilityOff()
      displayNode.SetVisibility(0)
    else:
      displayNode.SliceIntersectionVisibilityOn()
      displayNode.SetVisibility(1)

  def reformatNeedleID(self,ID):
    for i in range(2):  
      modelNode = slicer.util.getNode('vtkMRMLModelNode'+str(ID))
      polyData = modelNode.GetPolyData()
      nb = polyData.GetNumberOfPoints()
      base = [0,0,0]
      tip = [0,0,0]
      polyData.GetPoint(nb-1,tip)
      polyData.GetPoint(0,base)
      a,b,c = tip[0]-base[0],tip[1]-base[1],tip[2]-base[2]
      
      sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
      if sYellow ==None :
        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")        
      reformatLogic = slicer.vtkSlicerReformatLogic()
      sYellow.SetSliceVisible(1)
      reformatLogic.SetSliceNormal(sYellow,1,-a/b,0)
      m= sYellow.GetSliceToRAS()
      m.SetElement(0,3,base[0])
      m.SetElement(1,3,base[1])
      m.SetElement(2,3,base[2])
      sYellow.Modified()

  def setNeedleCoordinates(self):
    '''
    Apply the current transformation to the coordinates of the holes of the template
    self.p is defined in NFStep.py
    '''
    self.p = self.setHolesCoordinates()
    pNode = self.parameterNode()
    transformNodeID = pNode.GetParameter('followupTransformID')
    transformNode = slicer.mrmlScene.GetNodeByID(transformNodeID)
    if transformNode != None:
      transformMatrix = transformNode.GetMatrixTransformToParent()
      for i in xrange(63):
        vtkmat = vtk.vtkMatrix4x4()
        vtkmatOut = vtk.vtkMatrix4x4()
        vtkmat.SetElement(0,3,self.p[0][i])
        vtkmat.SetElement(1,3,self.p[1][i])

        vtkmat.Multiply4x4(transformMatrix,vtkmat,vtkmatOut)

        self.p[0][i] = vtkmatOut.GetElement(0,3)
        self.p[1][i] = vtkmatOut.GetElement(1,3)

    return self.p
                 
  def findLabelNeedleID(self,ID):
    '''
    Takes the needle (vtkMRMLModelNode) with the right ID
    Evaluates the z-position of every 20 points of the vtkPolyData
    Takes the closest one to the surface of the template holes
    Find the closest hole to the needle and assign the label to the needle 
    '''
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    imageData = volumeNode.GetImageData()
    imageDimensions = imageData.GetDimensions()
    m = vtk.vtkMatrix4x4()
    minZ=None
    mindist=None
    volumeNode.GetIJKToRASMatrix(m)
    Z = m.GetElement(2,3)
    needleNode = slicer.mrmlScene.GetNodeByID(ID)
    polydata = needleNode.GetPolyData()
    nb = polydata.GetNumberOfPoints()
    for i in range(nb):
      if 20*i<nb:
        pt=[0,0,0]
        polydata.GetPoint(20*i,pt)
        if (pt[2]-Z)**2<minZ or minZ == None:
          minZ = (pt[2]-Z)**2
          bestNB = 20*i
    hole = self.setNeedleCoordinates()
    #print bestNB
    A=[0,0,0]
    polydata.GetPoint(bestNB,A)
    for j in xrange(63):
      delta = ((hole[0][j]-(A[0]))**2+(hole[1][j]-A[1])**2)**(0.5)
      if delta < mindist or mindist == None:
        bestmatch = j
        mindist = delta
        
    result = [bestmatch,mindist]
    return result

  def computerPolydataAndMatrix(self):

    Cylinder = vtk.vtkCylinderSource()

    Cylinder.SetResolution(1000)
    Cylinder.SetCapping(1) 
    Cylinder.SetHeight( float(200.0) )
    Cylinder.SetRadius( float(1.0) )
    self.m_polyCylinder=Cylinder.GetOutput()
    
    quad = vtk.vtkQuadric()
    quad.SetCoefficients(1,1,1,0,0,0,0,1,0,0)
    sample = vtk.vtkSampleFunction()
    sample.SetModelBounds(-30,30,-60,60,-30,30)
    sample.SetCapping(0)
    sample.SetComputeNormals(1)
    sample.SetSampleDimensions(50,50,50)
    sample.SetImplicitFunction(quad)
    contour = vtk.vtkContourFilter()
    contour.SetInputConnection(sample.GetOutputPort())
    contour.ComputeNormalsOn()
    contour.ComputeScalarsOn()
    contour.GenerateValues(4,0,100)
    self.m_polyRadiation = contour.GetOutput()

    self.m_vtkmat = vtk.vtkMatrix4x4()
    self.m_vtkmat.Identity()

    RestruMatrix=vtk.vtkMatrix4x4()
    WorldMatrix=vtk.vtkMatrix4x4()
    Restru2WorldMatrix=vtk.vtkMatrix4x4()

    RestruMatrix.SetElement(0,0,0)
    RestruMatrix.SetElement(1,0,0)
    RestruMatrix.SetElement(2,0,0)
    RestruMatrix.SetElement(3,0,1)

    RestruMatrix.SetElement(0,1,1)
    RestruMatrix.SetElement(1,1,0)
    RestruMatrix.SetElement(2,1,0)
    RestruMatrix.SetElement(3,1,1)

    RestruMatrix.SetElement(0,2,0)
    RestruMatrix.SetElement(1,2,1)
    RestruMatrix.SetElement(2,2,0)
    RestruMatrix.SetElement(3,2,1)

    RestruMatrix.SetElement(0,3,0)
    RestruMatrix.SetElement(1,3,0)
    RestruMatrix.SetElement(2,3,1)
    RestruMatrix.SetElement(3,3,1)

    WorldMatrix.SetElement(0,0,0)
    WorldMatrix.SetElement(1,0,0)
    WorldMatrix.SetElement(2,0,0)
    WorldMatrix.SetElement(3,0,1)

    WorldMatrix.SetElement(0,1,1)
    WorldMatrix.SetElement(1,1,0)
    WorldMatrix.SetElement(2,1,0)
    WorldMatrix.SetElement(3,1,1)

    WorldMatrix.SetElement(0,2,0)
    WorldMatrix.SetElement(1,2,0)
    WorldMatrix.SetElement(2,2,-1)
    WorldMatrix.SetElement(3,2,1)

    WorldMatrix.SetElement(0,3,0)
    WorldMatrix.SetElement(1,3,1)
    WorldMatrix.SetElement(2,3,0)
    WorldMatrix.SetElement(3,3,1)

    WorldMatrix.Invert()
    Restru2WorldMatrix.Multiply4x4(RestruMatrix,WorldMatrix,self.m_vtkmat)
  
  def AddContour(self,polyData):
    '''
    Add caculated isosurfaces (self.drawIsoSurfaces) around visible needles to the scene
    and add opacity, color...
    '''
    #print polyData
    scene = slicer.mrmlScene
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    contourNode = None
    contourNode = slicer.util.getNode('Contours')
    if contourNode != None:
      slicer.mrmlScene.RemoveNode(contourNode.GetStorageNode())
      contourNode.RemoveAllDisplayNodeIDs()
      slicer.mrmlScene.RemoveNode(contourNode)        
  
    modelNode = slicer.vtkMRMLModelNode()
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
    displayNode.SetScalarRange(10,40)
    displayNode.SetBackfaceCulling(0)
    displayNode.SetScene(scene)
    scene.AddNode(displayNode)
    modelNode.SetAndObserveDisplayNodeID(displayNode.GetID())
    # add to scene
    displayNode.SetInputPolyData(modelNode.GetPolyData())
    scene.AddNode(modelNode)

    pNode= self.parameterNode()
    pNode.SetParameter('Contours',modelNode.GetID())

    qt.QApplication.processEvents()
      
  #----------------------------------------------------------------------------------------------
  ''' Needle Detection'''
  #----------------------------------------------------------------------------------------------

  def array2(self):
    '''
    Used if needle tips input is given trough a labelmap.
    Extract the coordinates of each labels (after IslandEffect)
    '''
    inputLabelID = self.__needleLabelSelector.currentNode().GetID()
    labelnode=slicer.mrmlScene.GetNodeByID(inputLabelID)
    i = labelnode.GetImageData()
    shape = list(i.GetDimensions())
    shape.reverse()
    a = vtk.util.numpy_support.vtk_to_numpy(i.GetPointData().GetScalars()).reshape(shape)
    labels=[]
    val=[[0,0,0] for i in range(a.max()+1)]
    for i in xrange(2,a.max()+1):
      w =numpy.transpose(numpy.where(a==i))
      # labels.append(w.mean(axis=0))
      val[i]=[0,0,0]
      val[i][0]=w[int(round(w.shape[0]/2))][2]
      val[i][1]=w[int(round(w.shape[0]/2))][1]
      val[i][2]=w[int(round(w.shape[0]/2))][0]
      if val[i] not in self.previousValues:
        labels.append(val[i])
        self.previousValues.append(val[i])
    return labels

  def factorial(self,n):
    '''
    factorial(n): return the factorial of the integer n.
    factorial(0) = 1
    factorial(n) with n<0 is -factorial(abs(n))
    '''
    result = 1
    for i in xrange(1, abs(n)+1):
     result *= i
    if n >= 0:
      return result
    else:
      return -result
      
  def binomial(self,n, k):
    if not 0 <= k <= n:
      return 0
    if k == 0 or k == n:
      return 1
    # calculate n!/k! as one product, avoiding factors that 
    # just get canceled
    P = k+1
    for i in xrange(k+2, n+1):
      P *= i
    # if you are paranoid:
    # C, rem = divmod(P, factorial(n-k))
    # assert rem == 0
    # return C
    return P//self.factorial(n-k)

  def Fibonacci(self,n):
    F=[0,1]
    for i in range(1,n+1):
      F.append(F[i-1]+F[i])
    return F

  def stepSize(self,k,l):
    '''
    The size of the step depends on:
    - the length of the needle
    - how many control points per needle 
    '''
    F = self.Fibonacci(l)
    s =F[k+1]/float(sum(self.Fibonacci(l)))
    return s

  def sortTable(self, table, cols):
    """ sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list 
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    for col in reversed(cols):
      table = sorted(table, key=operator.itemgetter(col))
    return table

  def sortTableReverse(self, table, cols):
    """ sort a table by multiple columns
        table: a list of lists (or tuple of tuples) where each inner list 
               represents a row
        cols:  a list (or tuple) specifying the column numbers to sort by
               e.g. (1,0) would sort by column 1, then by column 0
    """
    for col in reversed(cols):
      table = sorted(table, key=operator.itemgetter(col), reverse=True)
    return table

  def ijk2ras(self,A):
    '''
    Convert IJK coordinates to RAS coordinates. The transformation matrix is the one 
    of the active volume on the red slice
    '''
    m=vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    ras=[0,0,0]
    k = vtk.vtkMatrix4x4()
    o = vtk.vtkMatrix4x4()
    k.SetElement(0,3,A[0])
    k.SetElement(1,3,A[1])
    k.SetElement(2,3,A[2])
    k.Multiply4x4(m,k,o)
    ras[0] = o.GetElement(0,3)
    ras[1] = o.GetElement(1,3)
    ras[2] = o.GetElement(2,3)
    return ras

  def ras2ijk(self,A):
    '''
    Convert RAS coordinates to IJK coordinates. The transformation matrix is the one 
    of the active volume on the red slice
    '''
    m=vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    m.Invert()
    imageData = volumeNode.GetImageData()
    ijk=[0,0,0]
    k = vtk.vtkMatrix4x4()
    o = vtk.vtkMatrix4x4()
    k.SetElement(0,3,A[0])
    k.SetElement(1,3,A[1])
    k.SetElement(2,3,A[2])
    k.Multiply4x4(m,k,o)
    ijk[0] = o.GetElement(0,3)
    ijk[1] = o.GetElement(1,3)
    ijk[2] = o.GetElement(2,3)
    return ijk
  
  def needleDetection(self):
    '''
    This solution is optional but not used anymore in the workflow. 
    Use the label map of the needle tips
    Apply the island effect
    Extract the coordinates of the islands (self.array2)
    Start a detection for each island (self.needleDetectionThread)
    TODO: multi-processing
    '''
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
    parameterNode.SetParameter("IslandEffect,minimumSize",'0')
    islandTool.removeIslands()
    # select the image node from the Red slice viewer
    m=vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    spacing = volumeNode.GetSpacing()
    # chrono starts
    self.t0 = time.clock()
    # get the coordinates from the label map
    label=self.array2()
    for I in xrange(len(label)):
      A=label[I]
      colorVar = I/(len(label))
      self.needleDetectionThread(A, imageData, colorVar,spacing)
      if self.autoStopTip.isChecked():
        self.needleDetectionUPThread(A, imageData, colorVar,spacing)

  def needleValidation(self,A, imageData,colorVar,spacing):
    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    fiducial.SetName('.'+str(self.validationNeedleNumber)+"-"+str(self.stepNeedle)) 
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetFiducialCoordinates(self.ijk2ras(A))
    fiducial.SetAttribute('ValidationNeedle','1')
    fiducial.SetAttribute('NeedleNumber',str(self.validationNeedleNumber))
    fiducial.SetAttribute('NeedleStep',str(self.stepNeedle))
    
    nth = int(self.validationNeedleNumber)

    displayNode=fiducial.GetDisplayNode()
    displayNode.SetGlyphScale(2)
    displayNode.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
    textNode=fiducial.GetAnnotationTextDisplayNode()
    textNode.SetTextScale(4)
    textNode.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
    self.tableValueCtrPt[self.validationNeedleNumber][self.stepNeedle] = self.ijk2ras(A)


  def obturatorNeedle(self,A, imageData,colorVar,spacing):
    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetFiducialCoordinates(self.ijk2ras(A))
    fiducial.SetAttribute('ObturatorNeedle','1')
    if self.obtuNeedle <= 1:
      needleNumber = 0
    else:
      needleNumber = self.obtuNeedle-1
      needleStep = 0
    if self.obtuNeedle ==1:
      needleStep = 1
    elif self.obtuNeedle == 0:
      needleStep = 0

    fiducial.SetAttribute('NeedleNumber',str(needleNumber))
    fiducial.SetAttribute('NeedleStep',str(needleStep))
    fiducial.SetName(".obtu-"+str(needleNumber)) 
    
    nth = int(needleNumber)

    displayNode=fiducial.GetDisplayNode()
    displayNode.SetGlyphScale(2)
    displayNode.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
    textNode=fiducial.GetAnnotationTextDisplayNode()
    textNode.SetTextScale(4)
    textNode.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
    
    self.obtuNeedleValueCtrPt[needleNumber][needleStep] = self.ijk2ras(A)
    # print self.ijk2ras(A)
    #print "ctr pt: ",self.obtuNeedleValueCtrPt

    if needleNumber>=1:
      Vx = self.obtuNeedleValueCtrPt[0][1][0] - self.obtuNeedleValueCtrPt[0][0][0]
      Vy = self.obtuNeedleValueCtrPt[0][1][1] - self.obtuNeedleValueCtrPt[0][0][1]
      Vz = self.obtuNeedleValueCtrPt[0][1][2] - self.obtuNeedleValueCtrPt[0][0][2]

      L= float(Vx**2 + Vy**2 + Vz**2)**0.5

      E = self.ijk2ras(A)
      Ex = E[0] + 100*Vx/L
      Ey = E[1] + 100*Vy/L
      Ez = E[2] + 100*Vz/L
      self.obtuNeedleValueCtrPt[needleNumber][1] = [Ex,Ey,Ez]

    self.drawObturatorNeedles()
    self.stop()
    self.fiducialObturatorButton.checked = 1
    self.start(3)



  def objectiveFunction(self,imageData, ijk, radiusNeedleParameter, spacing, gradientPonderation):
    radiusNeedle        = int(round(radiusNeedleParameter/float(spacing[0])))
    radiusNeedleCorner  = int(round((radiusNeedleParameter/float(spacing[0])/1.414)))
    ijk[0]=int(round(ijk[0]))
    ijk[1]=int(round(ijk[1]))
    ijk[2]=int(round(ijk[2]))
    center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0]+1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+1, ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0]-1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-1, ijk[2], 0)

    if gradientPonderation != 0:
      g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
      g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
      g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
      g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
      g5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)                    
      g6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
      g7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)
      g8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)

      total = center/float(5) - ((g1+g2+g3+g4+g5+g6+g7+g8)/float(8))*gradientPonderation
    else:
      total = center/float(5)

    return total

  def objectiveFunctionLOG(self,imageData, ijk, radiusNeedleParameter, spacing, gradientPonderation):
    '''
    not used.
    idea was to test a different objective function
    '''
    radiusNeedle        = int(round(radiusNeedleParameter/float(spacing[0])))
    radiusNeedleCorner  = int(round((radiusNeedleParameter/float(spacing[0])/1.414)))
    
    center = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0]+1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+1, ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0]-1, ijk[1], ijk[2], 0)
    center += imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-1, ijk[2], 0)

    if gradientPonderation != 0:
      g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
      g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
      g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
      g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
      g5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)                    
      g6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
      g7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)
      g8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)

      total = center/float(5) - ((g1+g2+g3+g4+g5+g6+g7+g8)/float(8))
    else:
      total = center/float(5)

    return math.log(total/float(30)+0.1)

    
  #------------------------------------------------------------------------------ 
  #
  #
  ## FIND THE OPTIMAL TIP IN A CIRCLE (center = mouse click)
  #
  #
  #------------------------------------------------------------------------------

  def findTip(self, A, imageData, radiusNeedle, coeff, sigmaValue, gradientPonderation, X, Y, Z):
    minTotalTip=0
    X = int(X)
    Y = int(Y)
    Z = int(Z)
    for I in range(-X,X):
      i=I/float(coeff)
      for J in range(-Y,Y):
        j=J/float(coeff)
        for k in range(1):
          v0=0
          totalTip=0
          for l in range (-3,1):
            v0 = 8*imageData.GetScalarComponentAsDouble(A[0]+i, A[1]+j, A[2]+k+l, 0)
            
            v1 = imageData.GetScalarComponentAsDouble(A[0]+radiusNeedle+i, A[1]+j, A[2]+k+l, 0)
            v2 = imageData.GetScalarComponentAsDouble(A[0]-radiusNeedle+i, A[1]+j, A[2]+k+l, 0)
            v3 = imageData.GetScalarComponentAsDouble(A[0]+i, A[1]+radiusNeedle+j, A[2]+k+l, 0)
            v4 = imageData.GetScalarComponentAsDouble(A[0]+i, A[1]-radiusNeedle+j, A[2]+k+l, 0)
            
            totalTip += v0-((v1+v2+v3+v4)/float(4))*gradientPonderation
          
          rgauss      = (  i**2 
                            +j**2
                            +k**2 )**0.5

          gaussianAttenuation = math.exp(-(rgauss/float(10))**2/float((2*(sigmaValue/float(10))**2)))
          totalTip = gaussianAttenuation * totalTip 
          
          #totalTip = v0
          if totalTip<minTotalTip or minTotalTip==0:
            minTotalTip = totalTip
            IBest = A[0]+i
            JBest = A[1]+j
            KBest = A[2]+k
            P=[ 0 for n in range(5)]
            P[0] = [A[0]+i, A[1]+j, A[2]+k+l]
            P[1] = [A[0]+radiusNeedle+i, A[1]+j, A[2]+k+l]
            P[2] = [A[0]-radiusNeedle+i, A[1]+j, A[2]+k+l]
            P[3] = [A[0]+i, A[1]+radiusNeedle+j, A[2]+k+l]
            P[4] = [A[0]+i, A[1]-radiusNeedle+j, A[2]+k+l]
              
    '''
    # Draw template
    for pi in range(5):
      fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
      fiducial.Initialize(slicer.mrmlScene)
      fiducial.SetName(str(pi))
      fiducial.SetFiducialCoordinates(self.ijk2ras(P[pi]))
    '''
    #print "bestTip:",IBest,JBest,KBest, minTotalTip
    #print "initialtip:", A
    AInit=A

    A=[IBest,JBest,KBest]

    return A
  
  #------------------------------------------------------------------------------ 
  #
  #
  ## TRACKING NEEDLE IN -Z DIRECTION
  #
  #
  #------------------------------------------------------------------------------


  def needleDetectionThread(self,A, imageData,colorVar,spacing):
    '''
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    
    ### initialisation of the parameters
    ijk         = [0,0,0]
    bestPoint   = [0,0,0]
    mode        = "circle"

    ### load parameters from GUI
    distanceMax                 = self.distanceMax.value
    gradientPonderation         = self.gradientPonderation.value
    sigmaValue                  = self.sigmaValue.value
    stepsize                    = self.stepsize.value
    gaussianAttenuationChecked  = self.gaussianAttenuationButton.isChecked()
    lookNeighborhood            = self.gradient.isChecked()
    numberOfPointsPerNeedle     = max(1,self.numberOfPointsPerNeedle.value-1)
    nbRotatingIterations        = self.nbRotatingIterations.value
    radiusNeedleParameter       = self.radiusNeedleParameter.value
    axialSegmentationLimit      = self.axialSegmentationLimit
    lenghtNeedleParameter       = self.lenghtNeedleParameter.value/(spacing[2])

    ### length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)

    if axialSegmentationLimit!=None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit)*1.15*spacing[2]
    elif axialSegmentationLimit==None and self.maxLength.isChecked():
      axialSegmentationLimit = 0
      lenghtNeedle = abs(A[2] - axialSegmentationLimit)*1.15*spacing[2]
    else:
      lenghtNeedle = lenghtNeedleParameter
    
    rMax            = distanceMax/float(spacing[0])
    NbStepsNeedle   = numberOfPointsPerNeedle - 1
    nbRotatingStep  = nbRotatingIterations

    dims            = [0,0,0]
    imageData.GetDimensions(dims)
    pixelValue      = numpy.zeros(shape=(dims[0],dims[1],dims[2]))
    
    A0              = A
    #print A0
    
    self.controlPoints       = []
    controlPointsIJK    = []
    bestControlPoints   = []

    radiusNeedle        = int(round(radiusNeedleParameter/float(spacing[0])))
    radiusNeedleCorner  = int(round((radiusNeedleParameter/float(spacing[0])/1.414)))
    
    #---------------------------------------------------------------------------------
    # look for the best tip in the neighboorhood of the mouse click
    coeff = 1 # to look every 0.2mm
    radiusSphere=5
    X=coeff*radiusSphere/float(spacing[0])
    Y=coeff*radiusSphere/float(spacing[1])
    Z=5/float(spacing[2])
    #print "X,Y,Z",X,Y,Z
    #---------------------------------------------------------------------------------
    # find the tip in a circle
    if self.autoCorrectTip.isChecked():
      A = self.findTip(A,imageData, radiusNeedle, coeff, sigmaValue, gradientPonderation, X,Y,Z)
    # keep the first control point as A0
    A0=A
    #---------------------------------------------------------------------------------
    # Add points to the control point list    

    self.controlPoints.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))
    #---------------------------------------------------------------------------------
    # Draw fiducial points initial tip and found tip
    '''
    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetName('Best tip')
    fiducial.SetFiducialCoordinates(self.ijk2ras(A))
    fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    fiducial.Initialize(slicer.mrmlScene)
    fiducial.SetName('A init')
    fiducial.SetFiducialCoordinates(self.ijk2ras(AInit))
    '''
    
    for step in range(0,NbStepsNeedle+1):
      
      #step 0
      #------------------------------------------------------------------------------
      if step==0:

        stepSize  = self.stepSize(step,NbStepsNeedle)*lenghtNeedle

        Vx        = 0
        Vy        = 0
        Vz        = - stepSize

        rMax    = distanceMax/float(spacing[0])
        rIter   = int(round(rMax))
        tIter   = max(1,int(round(stepSize)))

        #print "stepsize 0:",stepSize
        
        tot     = stepSize

      #step 1,2,...
      #------------------------------------------------------------------------------
      #       [   vector V   ]
      #       *--------------*---------------------X   -> direction of tracking
      #      tip0            A                    C0
      #
      #      then, for the following step:
      #                                    tip0<-A, A<-C, C0 = A + K.V
     
      else:

        '''
        stepSize = self.stepSize(step+1,NbStepsNeedle+1)*lenghtNeedle
        #print '\nstepsize',step, ':',stepSize
        

        C0      = [ 2*A[0]-tip0[0],
                    2*A[1]-tip0[1],
                    A[2]-stepSize   ]
        '''


        stepSize  = self.stepSize(step+1,NbStepsNeedle+1)*lenghtNeedle
        rMax    = max(stepSize,distanceMax/float(spacing[0]))
        rIter   = max(15,min(20,int(rMax/float(spacing[0]))))
        tIter   = max(1,int(round(stepSize)))
      
        # Vector V    
        Vx        = A[0]-tip0[0]
        Vy        = A[1]-tip0[1]
        Vz        = A[2]-tip0[2]

      coeffSize = abs(stepSize)
      if Vz != 0 :
        K         = coeffSize/float(abs(Vz))
      else:
        break

      P0        = A
      C0        = [ P0[0] + K * Vx,
                    P0[1] + K * Vy,
                    P0[2] + K * Vz ]
        
      estimator     = 0
      minEstimator  = 0  

      #radius variation
      for R in range(rIter+1):

        r=R*(rMax/float(rIter))
        
        ### angle variation from 0 to 360
        for thetaStep in xrange(nbRotatingStep ):
          
          angleInDegree = (thetaStep*360)/float(nbRotatingStep)
          theta         = math.radians(angleInDegree)

          C             = [ C0[0]+r*(math.cos(theta)),
                            C0[1]+r*(math.sin(theta)),
                            C0[2]]

          total     = 0
          M         = [[0,0,0] for i in xrange(tIter+1)]
          
         
          # calculates tIter = number of points per segment 
          #print tIter
          for t in xrange(tIter+1):

            tt  = t/float(tIter)
            
            # x,y,z coordinates
            for i in range(3):
              
              M[t][i]   = (1-tt)*A[i] + tt*C[i]
              ijk[i]    = int(round(M[t][i]))
              
            # first, test if points are in the image space 
            if ijk[0]<dims[0] and ijk[0]>0 and  ijk[1]<dims[1] and ijk[1]>0 and ijk[2]<dims[2] and ijk[2]>0:
              
              center    =   imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]+1, ijk[1], ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]-1, ijk[1], ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+1, ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-1, ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]+1, ijk[1]+1, ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]+1, ijk[1]-1, ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]-1, ijk[1]+1, ijk[2], 0)
              center    +=  imageData.GetScalarComponentAsDouble(ijk[0]-1, ijk[1]-1, ijk[2], 0)

              total     += center**self.exponent.value
              if lookNeighborhood ==1 and mode == "circle" :
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
                g5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)                    
                g6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                g7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)
                g8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                
                #total += (center - ((g1+g2+g3+g4+g5+g6+g7+g8)/float(8))*gradientPonderation)/float(tIter)
                total += ((center - g1)**gradientPonderation)/float(tIter)
                total += ((center - g2)**gradientPonderation)/float(tIter)
                total += ((center - g3)**gradientPonderation)/float(tIter)
                total += ((center - g4)**gradientPonderation)/float(tIter)
                total += ((center - g5)**gradientPonderation)/float(tIter)
                total += ((center - g6)**gradientPonderation)/float(tIter)
                total += ((center - g7)**gradientPonderation)/float(tIter)
                total += ((center - g8)**gradientPonderation)/float(tIter)
               
                # total = self.objectiveFunctionLOG(imageData, ijk, radiusNeedleParameter, spacing, 1)

              if lookNeighborhood ==1 and mode == "square" :
                
                g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
                
                total += (8*center - ((g1+g2+g3+g4)/float(4))*gradientPonderation)/float(tIter)
               
                # total = self.objectiveFunctionLOG(imageData, ijk, radiusNeedleParameter, spacing, 1)

          if R == 0:
            
            initialIntensity    = total
            estimator           = total
            
          if gaussianAttenuationChecked==1 and step>=2 :
            if step == NbStepsNeedle:
                sigmaValue = 100
            
            if Vz != 0:
              ''' 
              stepSize    =(A[2] - C0[2])
              K           =stepSize/float(tip0[2]-A[2])

              X           = [ A[0] + K * (A[0]-tip0[0]),
                              A[1] + K * (A[1]-tip0[1]),
                              A[2] + K * (A[2]-tip0[2]) ]
              '''

              rgauss      = (  (C[0]-C0[0])**2 
                              +(C[1]-C0[1])**2
                              +(C[2]-C0[2])**2 )**0.5

              gaussianAttenuation = math.exp(-(rgauss/float(rMax))**2/float((2*(sigmaValue/float(10))**2)))   # 1 for x=0, 0.2 for x=5
              estimator           = (total)*gaussianAttenuation
            else:
              estimator = total


          else:
            estimator = (total)
       
          if estimator<initialIntensity:

            if estimator<minEstimator or minEstimator == 0:
              minEstimator  = estimator
              if minEstimator!=0:  
                bestPoint   = C
        
           
      tip0  = A
      if bestPoint==[0,0,0]:
        A   = C0
      elif bestPoint!=tip0: 
        A   = bestPoint

      # save the value of the objective function for the initial step.
      # will be used as reference for the initial step of the ascending tracking
      if step == 1:
        self.estimatorReference = minEstimator  
 

      if A[2]<axialSegmentationLimit and A!=A0:
        
        asl = axialSegmentationLimit
        l   = (A[2]-asl)/float(tip0[2]-A[2])

        A   =[  A[0] - l*(tip0[0]-A[0]),
                A[1] - l*(tip0[1]-A[1]),
                A[2] - l*(tip0[2]-A[2])]

      self.controlPoints.append(self.ijk2ras(A))
      controlPointsIJK.append(A)
      #print('step:',step,':',minEstimator )
      if self.drawFiducialPoints.isChecked():
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.'+str(minEstimator))
        fiducial.SetFiducialCoordinates(self.controlPoints[step+1])

      if A[2]<=axialSegmentationLimit and A!=A0:
        break
    
    if not self.autoStopTip.isChecked():
      self.addNeedleToScene(self.controlPoints,colorVar)
    



  #------------------------------------------------------------------------------ 
  #
  #
  ## TRACKING NEEDLE IN +Z DIRECTION
  #
  #
  #------------------------------------------------------------------------------

  def needleDetectionUPThread(self,A, imageData,colorVar,spacing):
    '''
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    
    ### initialisation of the parameters
    ijk         = [0,0,0]
    bestPoint   = [0,0,0]

    ### load parameters from GUI
    distanceMax                 = self.distanceMax.value
    gradientPonderation         = self.gradientPonderation.value
    sigmaValue                  = self.sigmaValue.value
    stepsize                    = self.stepsize.value
    gaussianAttenuationChecked  = self.gaussianAttenuationButton.isChecked()
    lookNeighborhood            = self.gradient.isChecked()
    numberOfPointsPerNeedle     = max(1,self.numberOfPointsPerNeedle.value-1)
    nbRotatingIterations        = self.nbRotatingIterations.value
    radiusNeedleParameter       = self.radiusNeedleParameter.value
    # radiusNeedleParameter       = 1
    axialSegmentationLimit      = self.axialSegmentationLimit
    lenghtNeedleParameter       = self.lenghtNeedleParameter.value/(spacing[2])

    ### length needle = distance Aijk[2]*0.9
    # lenghtNeedle = abs(self.ijk2ras(A)[2]*0.9)

    if axialSegmentationLimit!=None:
      lenghtNeedle = abs(A[2] - axialSegmentationLimit)*1.15*spacing[2]
    elif axialSegmentationLimit==None and self.maxLength.isChecked():
      axialSegmentationLimit = 0
      lenghtNeedle = abs(A[2] - axialSegmentationLimit)*1.15*spacing[2]
    else:
      lenghtNeedle = lenghtNeedleParameter
    
    rMax            = distanceMax/float(spacing[0])
    NbStepsNeedle   = numberOfPointsPerNeedle - 1
    nbRotatingStep  = nbRotatingIterations

    dims            =[0,0,0]
    imageData.GetDimensions(dims)
    pixelValue      = numpy.zeros(shape=(dims[0],dims[1],dims[2]))
    
    A0              = A
    #print A0
    
    controlPointsUP       = []
    controlPointsIJK    = []
    bestControlPoints   = []
    minEstimator0       = None
    stopTracking        = 0
    

    controlPointsUP.append(self.ijk2ras(A))
    controlPointsIJK.append(A)
    bestControlPoints.append(self.ijk2ras(A))
    
    radiusNeedle        = int(round(radiusNeedleParameter/float(spacing[0])))
    radiusNeedleCorner  = int(round((radiusNeedleParameter/float(spacing[0])/1.414)))
    '''
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
    '''


    for step in range(0,NbStepsNeedle+1):
      
      #step 0
      #------------------------------------------------------------------------------
      if step==0:

        stepSize  = self.stepSize(step,NbStepsNeedle)*lenghtNeedle

        Vx        = 0
        Vy        = 0
        Vz        = stepSize

        C0        = [A[0],A[1],A[2]+ stepSize]
        rMax      = stepSize/float(spacing[0])
        rIter     = int(round(rMax))
        tIter     = max(1,int(round(stepSize)))

        #print "stepsize 0:",stepSize
        
        # tot     = stepSize

      #step 1,2,...
      #------------------------------------------------------------------------------
      else:

        stepSize  = self.stepSize(step+1,NbStepsNeedle+1)*lenghtNeedle
      
        Vx        = A[0]-tip0[0]
        Vy        = A[1]-tip0[1]
        Vz        = A[2]-tip0[2]

      coeffSize = abs(stepSize)
      if Vz != 0 :
        K         = coeffSize/float(abs(Vz))
      else:
        break

      P0        = A
      P1        = [ P0[0] + K * Vx,
                    P0[1] + K * Vy,
                    P0[2] + K * Vz ]



      # value of the objective function. We want to minimize it.
      dichoStep     = 0
      continueDichotomy   = 1

      # In order to find the tip, if the last point is beyond the tip (tested function of 
      # the relative value of the objective function), we start a dichotomy
      # the dichotomy runs until a) point below the tip  or b) more than 7 loops

      while continueDichotomy==1 and dichoStep <=7 and stopTracking == 0 :
        # reset values
        estimator     = 0
        minEstimator  = 0
        dichoStep     += 1
        if step != 100:
          
          if dichoStep > 1:

            K         /= float(2)
            stepSize  /= float(2)

            if testSuccess ==1:
              P0 = P1
            else:
              P0 = P0

            P1    = [ P0[0] + K * Vx,
                      P0[1] + K * Vy,
                      P0[2] + K * Vz ]
          #print "\t----------------------------------------"
          #print '\nstepsize',step, ':', stepSize
          # tot     += stepSize

          '''
          C0      = [ 2*A[0]-tip0[0],
                      2*A[1]-tip0[1],
                      A[2]+stepSize   ]
          '''


          '''
          coeffSize   = abs(stepSize)
          K           = coeffSize/float(abs(Vz))

          
          C0           = [ A[0] + K * Vx,
                          A[1] + K * Vy,
                          A[2] + K * Vz ]
          '''

          C0      = P1

          rMax    = stepSize/float(spacing[0])
          rIter   = max(15,min(20,int(rMax/float(spacing[0]))))
          tIter   = max(3,int(round(stepSize)))
          #print "\trMax:",rMax, "rIter:",rIter, "tIter",tIter
          #print "\tP1:",P1[2]
      
        
        #radius variation
        for R in range(rIter+1):

          r=R*(rMax/float(rIter))
          
          ### angle variation from 0 to 360
          for thetaStep in xrange(nbRotatingStep ):
            
            angleInDegree = (thetaStep*360)/float(nbRotatingStep)
            theta         = math.radians(angleInDegree)

            C             = [ C0[0]+r*(math.cos(theta)),
                              C0[1]+r*(math.sin(theta)),
                              C0[2]]

            total     = 0
            M         = [[0,0,0] for i in xrange(tIter+1)]
            
           
            # calculates tIter = number of points per segment 
            for t in xrange(tIter+1):

              tt  = t/float(tIter)
              
              # x,y,z coordinates
              for i in range(3):
                
                M[t][i]   = (1-tt)*A[i] + tt*C[i]
                ijk[i]    = int(round(M[t][i]))
                
              # first, test if points are in the image space 
              if ijk[0]<dims[0] and ijk[0]>0 and  ijk[1]<dims[1] and ijk[1]>0 and ijk[2]<dims[2] and ijk[2]>0:
                
                center    = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
                total     += center/float(tIter)
                if lookNeighborhood ==1 :

                  
                  
                  g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
                  g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
                  g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
                  g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
                  g5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)                    
                  g6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                  g7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)
                  g8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                  
                  total += (8*center - ((g1+g2+g3+g4+g5+g6+g7+g8)/float(8))*gradientPonderation)/float(tIter)
                
            if R==0:
              
              initialIntensity    = total
              estimator           = total
              
            if gaussianAttenuationChecked==1 and step>=1 :
              
              if Vz!=0:

                  '''
                  coeffSize    =abs((A[2] - C0[2]))
                  K           =coeffSize/float(abs(tip0[2]-A[2]))

                  X           = [ A[0] + K * (A[0]-tip0[0]),
                                  A[1] + K * (A[1]-tip0[1]),
                                  A[2] + K * (A[2]-tip0[2]) ]
                  '''

                  rgauss      = (  (C[0]-C0[0])**2 
                                  +(C[1]-C0[1])**2
                                  +(C[2]-C0[2])**2 )**0.5

                  gaussianAttenuation = math.exp(-(rgauss/float(rMax))**2/float((2*(sigmaValue/float(10))**2)))   # 1 for x=0, 0.2 for x=5
                  estimator           = (total)*gaussianAttenuation
              else:
                  estimator = total


            else:
              estimator = (total)
         
            if estimator<initialIntensity:

              if estimator<minEstimator or minEstimator == 0:
                minEstimator  = estimator
                
                if minEstimator!=0:  
                  bestPoint   = C
          
             
        #print "\tInitial Intensity:",initialIntensity
        #print "\tMin Estimator:",minEstimator
        
        if step == 0:
          minEstimator0 = self.estimatorReference

        if minEstimator0 != None and minEstimator0 !=0:
          RelMinEstimator = abs((minEstimator-minEstimator0)/float(minEstimator0))
          
          #print "\tmin Estimator 0 :",minEstimator0,"\n"
          #print "\tRel Estimator :",RelMinEstimator,"\n"
          valCtrPt = self.objectiveFunction(imageData, A, 3, spacing, 1)
          #print "\tObjective function Ctl Pt: ", valCtrPt

          if dichoStep >= 8:
            stopTracking = 1
            bestPoint = A
            break
          if ((RelMinEstimator < 0.6) and valCtrPt < 0 and minEstimator0 <0) or (minEstimator < -80 and valCtrPt < 0):
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
      tip0  = A
      if bestPoint==[0,0,0]:    # if the initial point (center of the cone) is indeed the optimal ctrl point
        A   = C0
      elif bestPoint!=tip0: 
        A   = bestPoint
 
     
      

      controlPointsUP.append(self.ijk2ras(A))
      controlPointsIJK.append(A)

      if self.drawFiducialPoints.isChecked():
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.'+str(step)+'.'+str(self.objectiveFunction(imageData, A, 3, spacing, 1)))
        fiducial.SetFiducialCoordinates(controlPointsUP[step+1])

      if A[2]<=axialSegmentationLimit and A!=A0:
        break
    
    for i in range(len(controlPointsUP)):
      self.controlPoints.append(controlPointsUP[i])
    self.addNeedleToScene(self.controlPoints,colorVar)
    # print 'length:',tot

  def drawObturatorNeedles(self):
    '''
    Draw needles around the obturator of length self.realNeedleLength.value
    Draw straigth lines, parallel to the one defined by two control points
    given by the first two clicks
    '''


    # reset report table
    self.table =None
    self.row=0
    self.initTableView()
    while slicer.util.getNodes('obturator-seg*') != {}:
      nodes = slicer.util.getNodes('obturator-seg*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
    
    if self.obtuNeedleValueCtrPt==[[[]]]:
      self.obtuNeedleValueCtrPt = [[[999,999,999] for i in range(10)] for j in range(10)]
    if self.obtuNeedlePt==[[[]]]:
      self.obtuNeedlePt = [[[999,999,999] for i in range(10)] for j in range(10)]
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
    nbNode=modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
      modelNode=slicer.mrmlScene.GetNthNodeByClass(nthNode,'vtkMRMLAnnotationFiducialNode')
      if modelNode.GetAttribute("ObturatorNeedle") == "1":
        needleNumber = int(modelNode.GetAttribute("NeedleNumber"))
        needleStep = int(modelNode.GetAttribute("NeedleStep"))
        coord=[0,0,0]
        modelNode.GetFiducialCoordinates(coord)
        if needleNumber==0:
          self.obtuNeedleValueCtrPt[needleNumber][needleStep]=coord
        
    for i in range(0,len(self.obtuNeedleValueCtrPt)):

      sign = cmp(self.obtuNeedleValueCtrPt[0][0][2],self.obtuNeedleValueCtrPt[0][1][2])
      if (i==0 and sign <=-1 ):
        AA = self.obtuNeedleValueCtrPt[0][0][2]
        BB = self.obtuNeedleValueCtrPt[0][1][2]
        self.obtuNeedleValueCtrPt[0][0][2] = BB
        self.obtuNeedleValueCtrPt[0][1][2] = AA


      # As we give the tip of the obturator needles, we only want to g in the increasing z direction.

      Vx = self.obtuNeedleValueCtrPt[0][1][0] - self.obtuNeedleValueCtrPt[0][0][0]
      Vy = self.obtuNeedleValueCtrPt[0][1][1] - self.obtuNeedleValueCtrPt[0][0][1]
      Vz = self.obtuNeedleValueCtrPt[0][1][2] - self.obtuNeedleValueCtrPt[0][0][2]

      L= float(Vx**2 + Vy**2 + Vz**2)**0.5

      E = self.obtuNeedleValueCtrPt[i][0]
      Ex = E[0] + self.realNeedleLength.value*Vx/L
      Ey = E[1] + self.realNeedleLength.value*Vy/L
      Ez = E[2] + self.realNeedleLength.value*Vz/L
      self.obtuNeedlePt[i][1] = [Ex,Ey,Ez]
      self.obtuNeedlePt[i][0] = [E[0],E[1],E[2]]
          #print needleNumber,needleStep,coord


    for i in range(len(self.obtuNeedlePt)):
      if self.obtuNeedlePt[i][0][0]!=999:
          colorVar = random.randrange(50,100,1)/(100)
          controlPointsUnsorted = [val for val in self.obtuNeedlePt[i] if val !=[999,999,999]]
          controlPoints=controlPointsUnsorted
          #controlPoins = self.obtuNeedlePt[i]
          if ((i==0 and len(controlPoints)>=1) or i>=1) :
            self.addNeedleToScene(controlPoints,i,'Obturator')
      


  def drawValidationNeedles(self):

    # reset report table
    self.table =None
    self.row=0
    self.initTableView()
    while slicer.util.getNodes('manual-seg*') != {}:
        nodes = slicer.util.getNodes('manual-seg*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)
    
    if self.tableValueCtrPt==[[]]:
        self.tableValueCtrPt = [[[999,999,999] for i in range(100)] for j in range(100)]
    modelNodes = slicer.mrmlScene.GetNodesByClass('vtkMRMLAnnotationFiducialNode')
    nbNode=modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
        modelNode=slicer.mrmlScene.GetNthNodeByClass(nthNode,'vtkMRMLAnnotationFiducialNode')
        if modelNode.GetAttribute("ValidationNeedle") == "1":
          needleNumber = int(modelNode.GetAttribute("NeedleNumber"))
          needleStep = int(modelNode.GetAttribute("NeedleStep"))
          coord=[0,0,0]
          modelNode.GetFiducialCoordinates(coord)
          self.tableValueCtrPt[needleNumber][needleStep]=coord
          #print needleNumber,needleStep,coord



    for i in range(len(self.tableValueCtrPt)):
      if self.tableValueCtrPt[i][0][0]!=999:
          colorVar = random.randrange(50,100,1)/(100)
          controlPointsUnsorted = [val for val in self.tableValueCtrPt[i] if val !=[999,999,999]]
          controlPoints=self.sortTable(controlPointsUnsorted,(2,1,0))
          #print self.tableValueCtrPt[i]
          self.addNeedleToScene(controlPoints,i,'Validation')   

  def addNeedleToScene(self,controlPoint,colorVar, needleType='Detection'): 
    '''
    Create a model of the needle from its equation (Beziers curve fitting the control points)
    '''
    
    
    # sort the points in a decreasing order (from tip to bottom)
    controlPointListSorted=self.sortTableReverse(controlPoint,(2,1,0))

    # calculate the length of the list of ctr points
    lenghtTotal = 0
    for i in range(len(controlPoint)-1):
        lenghtTotal += self.distanceTwoPoints(controlPointListSorted[i+1],controlPointListSorted[i])
  
    #print 'lenght tube: ', lenghtTotal
    


    # in case we want to extend the needle to the wanted length
    '''
    The extension is currently done by adding a point to the control point list.
    TODO: only append a straight tube, so it doesn't add a control point and modify
    the initial Bezier curve
    '''
    if lenghtTotal < self.realNeedleLength.value and self.extendNeedle.isChecked():
      lastPoint = [controlPointListSorted[-1][0],controlPointListSorted[-1][1],controlPointListSorted[-1][2]-(self.realNeedleLength.value - lenghtTotal)]
      controlPointListSorted.append(lastPoint)

    label=None
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
    polyData.SetPolys( polygons )
    idArray = polygons.GetData()
    idArray.Reset()
    idArray.InsertNextTuple1(0)
    nbEvaluationPoints=50
    n = len(controlPointListSorted)-1
    Q=[[0,0,0] for t in range(nbEvaluationPoints+1)]
    # start calculation
    for t in range(nbEvaluationPoints):
      tt = float(t)/(1*nbEvaluationPoints)
      for j in range(3):
        for i in range(n+1):
          Q[t][j]+=self.binomial(n,i)*(1-tt)**(n-i)*tt**i*controlPointListSorted[i][j]
          
      pointIndex = points.InsertNextPoint(*Q[t])
      linesIDArray.InsertNextTuple1(pointIndex)
      linesIDArray.SetTuple1( 0, linesIDArray.GetNumberOfTuples() - 1 )
      lines.SetNumberOfCells(1)
    ### Create model node
    model = slicer.vtkMRMLModelNode()
    model.SetScene(scene)
    model.SetAndObservePolyData(polyData)
    ### Create display node
    modelDisplay = slicer.vtkMRMLModelDisplayNode()

    modelDisplay.SetScene(scene)
    scene.AddNode(modelDisplay)
    model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
    ### Add to scene
    modelDisplay.SetInputPolyData(model.GetPolyData())
    scene.AddNode(model)
    ###Create Tube around the line
    tube=vtk.vtkTubeFilter()
    polyData = model.GetPolyData()
    tube.SetInput(polyData)
    tube.SetRadius(1)
    tube.SetNumberOfSides(50)
    tube.Update()
    
    model.SetAndObservePolyData(tube.GetOutput())
    model.GetDisplayNode().SliceIntersectionVisibilityOn()
    if needleType=='Validation':
      model.SetName('manual-seg_'+str(colorVar))
    elif needleType=='Obturator':
      model.SetName('obturator-seg_'+str(colorVar))
    else:
      model.SetName('python-catch-round_'+str(self.round)+'-ID-'+str(model.GetID()))
    model.SetAttribute('type',needleType)
    
    # evaluate and print the processing time
    processingTime = time.clock()-self.t0
    # print processingTime

    # if registration has been done, find the label for the needle
    if self.transform!=None:
      label = self.findLabelNeedleID(model.GetID())
      #print label
      modelDisplay.SetColor(self.color[label[0]][0],self.color[label[0]][1],self.color[label[0]][2])
      model.SetAttribute("nth",str(label[0]))
    
    elif needleType=='Validation':
      nth = int(colorVar)%64
      modelDisplay.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
      model.SetAttribute("nth",str(nth)) 
    
    else:
      nth = int(model.GetID().strip('vtkMRMLModelNode'))%64
      modelDisplay.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
      model.SetAttribute("nth",str(nth))
    
    if needleType=='Validation':
      self.addSegmentedNeedleToTable(int(colorVar),label,'Validation')
    
    else:
      self.addSegmentedNeedleToTable(int(model.GetID().strip('vtkMRMLModelNode')),label)

  def deleteSegmentedNeedle(self):
    '''
    Delete every segmented needles of the current round
    '''
    while slicer.util.getNodes('python-catch-round_'+str(self.round)+'*') != {}:
      nodes = slicer.util.getNodes('python-catch-round_'+str(self.round)+'*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)

  def newInsertionNeedle(self):
    '''
    Start a new round
    '''
    messageBox = qt.QMessageBox.information( self, 'Information','You are creating a new set of needles')
    self.round +=1
    self.newInsertionButton.setText('Start a new set of needles - Round ' + str(self.round+1)+'?')
    self.deleteNeedleButton.setText('Delete Needles from round ' + str(self.round))

  def resetNeedleDetection(self):
    '''
    Reset the needle detection to completely start over.
    '''
    ret = messageBox = qt.QMessageBox.question( self, 'Attention','''
      Are you sure that you want to reset the needle detection? 
      It will delete every segmented needles...
      ''',qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    if ret == qt.QMessageBox.Ok:
      while slicer.util.getNodes('python-catch*') != {}:
        nodes = slicer.util.getNodes('python-catch*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)
      self.previousValues=[[0,0,0]]
      self.round=1
      self.newInsertionButton.setText('Start a new set of needles - Round ' + str(self.round+1)+'?')
      self.deleteNeedleButton.setText('Delete Needles from round ' + str(self.round))
      # reset report table
      self.table =None
      self.row=0
      self.initTableView()

  def resetNeedleValidation(self):
    '''
    Reset the needle detection to completely start over.
    '''
    ret = messageBox = qt.QMessageBox.question( self, 'Attention','''
      Are you sure that you want to reset the needle validation? 
      It will delete every segmented needles and the control points...
      ''',qt.QMessageBox.Ok, qt.QMessageBox.Cancel)
    if ret == qt.QMessageBox.Ok:
      while slicer.util.getNodes('manual-seg*') != {}:
        nodes = slicer.util.getNodes('manual-seg*')
        for node in nodes.values():
          slicer.mrmlScene.RemoveNode(node)

      while slicer.util.getNodes('.*') != {}:
        nodes = slicer.util.getNodes('.*')
        for node in nodes.values():
          if node.GetAttribute("ValidationNeedle") == "1":
            slicer.mrmlScene.RemoveNode(node)

      # reset report table
      self.table =None
      self.row=0
      self.initTableView()
    
    self.validationNeedleNumber=0
    self.stepNeedle = 0
    self.tableValueCtrPt=[[[999,999,999] for i in range(100)] for j in range(100)]

  def changeCursor(self,cursorNumber):
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
    self.scrollPointButton.setText('Scroll Point for Needle ' + str(self.editNeedleTxtBox.value)+ ' (pt: '+str(self.ptNumber)+')')

  def scrollPoint(self):
    self.changeValue()
    needle = self.editNeedleTxtBox.value
    #print self.ptNumber
    #print needle
    coord=[0,0,0]
    ptName = '.'+str(needle)+'-'+str(self.ptNumber)
    #print ptName
    modelNode = slicer.util.getNode(ptName)
    if modelNode != None:
        self.ptNumber=self.ptNumber+1
        if modelNode.GetAttribute("ValidationNeedle") == "1":
          modelNode.GetFiducialCoordinates(coord)
          X=coord[0]
          Y=coord[1]
          Z=coord[2]
    
        sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
        if sRed ==None :
          sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode1")

        sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
        if sYellow ==None :
          sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
        
        sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        if sGreen ==None :
          sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode3")           

        mYellow= sYellow.GetSliceToRAS()
        mYellow.SetElement(0,3,X)
        sYellow.Modified()
        sYellow.UpdateMatrices()

        mGreen= sGreen.GetSliceToRAS()
        mGreen.SetElement(1,3,Y)
        sGreen.Modified()
        sGreen.UpdateMatrices()

        mRed= sRed.GetSliceToRAS()
        mRed.SetElement(2,3,Z)
        sRed.Modified()
        sRed.UpdateMatrices()
    elif self.ptNumber!=0:
        self.ptNumber=0
        self.scrollPoint()


  def start(self,process=0):
    '''
    Start to observe the mouse clicks given by user (clicks on needle tips)
    '''   
    self.changeCursor(1)
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
        events = ("LeftButtonPressEvent","LeftButtonReleaseEvent", "EnterEvent", "LeaveEvent","KeyPressEvent","KeyReleaseEvent")
        for event in events:
          if process==1:
            tag = style.AddObserver(event, self.processEventNeedleValidation)
          elif process==2:
            tag = style.AddObserver(event, self.processEventAddManualTips)
          elif process==3:
            tag = style.AddObserver(event, self.processEventAddObturatorNeedleTips)
            dn = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode().GetDisplayNode()
            w = dn.GetWindow()
            l = dn.GetLevel()
            dn.AddObserver(vtk.vtkCommand.ModifiedEvent, lambda c,e : self.setWL(dn,w,l))
          else:
            tag = style.AddObserver(event, self.processEvent)   
          self.styleObserverTags.append([style,tag])

  def stop(self):
    '''
    Stop to observe the mouse clicks given by user
    '''
    self.changeCursor(0)
    self.removeObservers()
    self.fiducialObturatorButton.checked = 0
    self.fiducialButton.checked = 0
    self.validationNeedleButton.checked = 0



  def removeObservers(self):
    '''
    Remove observers and reset
    '''
    for observee,tag in self.styleObserverTags:
      observee.RemoveObserver(tag)
    self.styleObserverTags = []
    self.sliceWidgetsPerStyle = {}

  def processEvent(self,observee,event=None):
    '''
    Get the mouse clicks and create a fiducial node at this position. Used later for the fiducial registration
    '''
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "KeyPressEvent":
      sliceWidget = self.sliceWidgetsPerStyle[observee]
      style = sliceWidget.sliceView().interactorStyle()
      key = style.GetInteractor().GetKeySym()
      if key == 'o':
        self.numberOfPointsPerNeedle.setValue(3)
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "KeyReleaseEvent":
      self.numberOfPointsPerNeedle.setValue(6)

    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":


      if slicer.app.repositoryRevision<= 21022:
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
      
      colorVar = random.randrange(50,100,1)/(100)
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      ijk=self.ras2ijk(ras)
      
      self.t0=time.clock()
      self.needleDetectionThread(ijk, imageData, colorVar,spacing)
      if self.autoStopTip.isChecked():
        self.needleDetectionUPThread(ijk, imageData, colorVar,spacing)
      

  def processEventNeedleValidation(self,observee,event=None):
    '''
    Get the mouse clicks and create a fiducial node at this position. 
    '''
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision<= 21022:
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
      
      colorVar = random.randrange(50,100,1)/(100)
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      ijk=self.ras2ijk(ras)
      self.t0=time.clock()
      self.needleValidation(ijk, imageData, colorVar,spacing)
      self.stepNeedle+=1

    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeaveEvent":
      self.stop()


  def processEventAddObturatorNeedleTips(self,observee,event=None):
    '''
    Get the mouse clicks and create a fiducial node at this position. 
    '''
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision<= 21022:
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
      
      colorVar = random.randrange(50,100,1)/(100)
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      imageData = volumeNode.GetImageData()
      spacing = volumeNode.GetSpacing()
      ijk=self.ras2ijk(ras)
      self.t0=time.clock()
      self.obturatorNeedle(ijk, imageData, colorVar,spacing)
      self.obtuNeedle += 1

    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeaveEvent":
      self.stop()

  def processEventAddManualTips(self,observee,event=None):
    '''
    Get the mouse clicks and create a fiducial node at this position. Used later for the fiducial registration
    '''
    if self.sliceWidgetsPerStyle.has_key(observee) and event == "LeftButtonPressEvent":
      if slicer.app.repositoryRevision<= 21022:
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
      self.addManualTip(ras)




  def onRunButtonToggled(self, checked):
    if checked:
      self.startGivingControlPointsButton.checked = 0
      self.fiducialObturatorButton.checked = 0
      self.start()
      self.fiducialButton.text = "Stop Giving Tips"  
    else:
      self.stop()
      self.fiducialButton.text = "Start Giving Needle Tips"

  def onRunObturatorButtonToggled(self, checked):
    if checked:
      self.fiducialButton.checked = 0
      self.fiducialButton.text = "Start Giving Needle Tips"
      self.startGivingControlPointsButton.checked = 0
      self.start(3)
      self.fiducialObturatorButton.text = "Stop Giving Obturator Needle Tips"  
    else:
      self.stop()
      self.fiducialObturatorButton.text = "Start Giving Obturator Needle Tips"

  def onNeedleValidationButtonToggled(self, checked):
    if checked:
      self.fiducialObturatorButton.checked = 0
      self.fiducialButton.checked = 0
      self.fiducialButton.text = "Start Giving Needle Tips"
      self.start(1)
      self.startGivingControlPointsButton.text = "Stop Giving Control Points"  
    else:
      self.stop()
      self.startGivingControlPointsButton.text = "Start Giving Control Points"

  def validationNeedle(self):
    self.validationNeedleNumber += 1
    self.validationNeedleButton.text= "New Validation Needle: ("+str(self.validationNeedleNumber)+")->("+str(self.validationNeedleNumber+1)+")"
    # self.tableValueCtrPt.append([])
    self.stepNeedle = 0     

  #----------------------------------------------------------------------------------------------
  ''' Needle segmentation report'''
  #---------------------------------------------------------------------------------------------- 
  
  def initTableView(self):
    '''
    Initialize a table gathering information on segmented needles
    Model and view for stats table
    '''
    if self.table==None:
      self.keys = ("Label","Round" ,"Reliability")
      self.labelStats = {}
      self.labelStats['Labels'] = []
      self.items = []
      self.model = qt.QStandardItemModel()
      self.model.setColumnCount(6)
      self.model.setHeaderData(0,1,"")
      self.model.setHeaderData(1,1,"Label")
      self.model.setHeaderData(2,1,"R.")
      self.model.setHeaderData(3,1,"Reliability")
      self.model.setHeaderData(4,1,"Display")
      self.model.setHeaderData(5,1,"Reformat")
      if self.view == None:
        self.view = qt.QTableView()
        self.view.setMinimumHeight(300)
        self.view.sortingEnabled = True
        self.view.verticalHeader().visible = False
      # col = 1
      # for k in self.keys:
      #   # self.view.setColumnWidth(col,15*len(k))
      #   # self.model.setHeaderData(col,1,k)
      #   col += 1 
      self.view.setModel(self.model)
      self.view.setColumnWidth(0,18)
      self.view.setColumnWidth(1,58)
      self.view.setColumnWidth(2,28)
      self.table = 1

  def addSegmentedNeedleToTable(self,ID,label=None,needleType=None):
    '''
    Add last segmented needle to the table
    The color icon corresponds to the color of the needle, which corresponds to its label (color code)
    '''
    self.initTableView()
    if label !=None:
      ref = int(label[0])
      needleLabel = self.option[ref]
      reliability = label[1]
    else:
      needleLabel = str(ID)
      ref = ID
      reliability = '-'
    # ref = int(modelNode.GetAttribute("nth"))
    
    self.labelStats["Labels"].append(ref)
    self.labelStats[ref,"Label"] = needleLabel
    self.labelStats[ref,"Round"] = str(self.round)
    self.labelStats[ref,"Reliability"] = str(reliability) 
      
    color = qt.QColor()
    color.setRgb(self.color255[ref][0],self.color255[ref][1],self.color255[ref][2])
    item = qt.QStandardItem()
    item.setData(color,1)
    self.model.setItem(self.row,0,item)
    self.items.append(item)
    col = 1
    for k in self.keys:
      item = qt.QStandardItem()
      item.setText(self.labelStats[ref,k])
      self.model.setItem(self.row,col,item)
      self.items.append(item)
      col += 1
    displayButton = qt.QPushButton("Display")
    displayButton.checked = True
    displayButton.checkable = True
    if needleType=='Validation':
      ID=int(slicer.util.getNode('manual-seg_'+str(ID)).GetID().strip('vtkMRMLModelNode'))
    displayButton.connect("clicked()", lambda who=ID: self.displayNeedleID(who))
    index = self.model.index(self.row,4)
    self.view.setIndexWidget(index,displayButton)
    reformatButton = qt.QPushButton("Reformat")
    reformatButton.connect("clicked()", lambda who=ID: self.reformatNeedleID(who))
    index2 = self.model.index(self.row,5)
    self.view.setIndexWidget(index2,reformatButton)
    self.row += 1  
  
    self.analysisGroupBoxLayout.addRow(self.view)

  #-----------------------------------------------------------
  # Radiation

  def AddRadiation(self,i,needleID):
    '''
    Goal of this function is to draw quadrics simulating the dose radiation.
    Currently, ellipse is a too naive model.
    This project might be continuated later
    '''
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
  '''
  The purpose of the following functions is to process the results of the needle segmentation from 
  Yi Gao's CLI module.
  Currently, another solution has been chosen but this could be usefull again later.
  To use it, simply uncommented the corresponding buttons in "createUserInterface"
  '''
  #----------------------------------------------------------------------------------------------
  def analyzeSegmentation(self):
    '''
    not used anymore. 
    '''
    if self.analysisGroupBox != None:
      self.__layout.removeWidget(self.analysisGroupBox)
      self.analysisGroupBox.deleteLater()
      self.analysisGroupBox = None
    self.analysisGroupBox = qt.QGroupBox()
    self.analysisGroupBox.setFixedHeight(600)
    self.analysisGroupBox.setTitle( 'Segmentation Report' )
    self.__layout.addRow( self.analysisGroupBox )
    self.analysisGroupBoxLayout = qt.QFormLayout( self.analysisGroupBox )
    if self.transform !=None :
      # transformation matrix
      m = self.transform.GetMatrixTransformToParent()
      m_t = vtk.vtkMatrix4x4()
      m_t.DeepCopy(m)
      
      # data from a the first planned-needle found
      modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
      stop = 1
      for modelNode in modelNodes.values():
        if modelNode.GetAttribute("planned") == "1" and stop:
          stop = 0
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          # evaluate the angle after the coordinate system transformation - used after as reference
          vtkmat = vtk.vtkMatrix4x4()              
          vtkmat.SetElement(0,3,base[0])       
          vtkmat.SetElement(1,3,base[1])
          vtkmat.SetElement(2,3,base[2])       
          m_t.Multiply4x4(m_t,vtkmat,vtkmat)
          base[0] = vtkmat.GetElement(0,3)      
          base[1] = vtkmat.GetElement(1,3)
          base[2] = vtkmat.GetElement(2,3)
          vtkmat = vtk.vtkMatrix4x4()              
          vtkmat.SetElement(0,3,tip[0])       
          vtkmat.SetElement(1,3,tip[1]) 
          vtkmat.SetElement(2,3,tip[2])      
          m_t.Multiply4x4(m_t,vtkmat,vtkmat)
          tip[0] = vtkmat.GetElement(0,3)       
          tip[1] = vtkmat.GetElement(1,3)
          tip[2] = vtkmat.GetElement(2,3)

          phi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]-base[1])**2)**0.5))
          theta1 = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
          psi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[2]-base[2])**2)**0.5))
           

      m = vtk.vtkMatrix4x4()
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      volumeNode.GetIJKToRASMatrix(m)
      m.Invert()
      imageData = volumeNode.GetImageData()
      indice=0
      
      # model and view for stats table
      self.keys = ("Label", "Intensity Average","Angle Deviation")
      self.view = qt.QTableView()
      self.view.setMinimumHeight(300)
      self.labelStats = {}
      self.labelStats['Labels'] = []
      self.view.sortingEnabled = True
      self.items = []
      self.model = qt.QStandardItemModel()
      self.view.setModel(self.model)
      self.view.verticalHeader().visible = False
      row = 0
      modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
      for modelNode in modelNodes.values():
        displayNode = modelNode.GetDisplayNode()
        if modelNode.GetAttribute("segmented") == "1" and displayNode.GetVisibility()==1:        
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          ijk=[0,0,0]
          ras=[0,0,0]
          total=0
          for i in range(nb):
            polyData.GetPoint(i,ras)
            k = vtk.vtkMatrix4x4()
            o = vtk.vtkMatrix4x4()
            k.SetElement(0,3,ras[0])
            k.SetElement(1,3,ras[1])
            k.SetElement(2,3,ras[2])
            k.Multiply4x4(m,k,o)
            ijk[0] = int(round(o.GetElement(0,3)))
            ijk[1] = int(round(o.GetElement(1,3)))
            ijk[2] = int(round(o.GetElement(2,3)))
            pixelValue = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
            total += pixelValue
          indice = total/(nb-1)

          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          phi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]*100-base[1]*100)**2)**0.5))
          theta = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
          psi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]-base[0])**2+(tip[2]-base[2])**2)**0.5))
          angleDeviation = (phi1-phi)**2+(theta1-theta)**2+(psi1-psi)**2
        
          # result = "Needle " + self.option[int(modelNode.GetAttribute("nth"))] + ": Angle Deviation from ref: " + str(angleDeviation)+" Intensity average :" + str(indice) 
          # analysisLine = qt.QLabel(result)
          # self.analysisGroupBoxLayout.addRow(analysisLine)
          
          self.labelStats["Labels"].append(int(modelNode.GetAttribute("nth")))
          self.labelStats[int(modelNode.GetAttribute("nth")),"Label"] = self.option[int(modelNode.GetAttribute("nth"))]
          self.labelStats[int(modelNode.GetAttribute("nth")),"Intensity Average"] = indice
          self.labelStats[int(modelNode.GetAttribute("nth")),"Angle Deviation"] = angleDeviation 
                
      for i in self.labelStats["Labels"]:
        color = qt.QColor()
        color.setRgb(self.color255[i][0],self.color255[i][1],self.color255[i][2])
        item = qt.QStandardItem()
        item.setData(color,1)
        self.model.setItem(row,0,item)
        self.items.append(item)
        col = 1
        for k in self.keys:
          item = qt.QStandardItem()
          item.setText(self.labelStats[i,k])
          self.model.setItem(row,col,item)
          self.items.append(item)
          col += 1
        row += 1

      self.view.setColumnWidth(0,30)
      self.model.setHeaderData(0,1," ")
      col = 1
      for k in self.keys:
        self.view.setColumnWidth(col,15*len(k))
        self.model.setHeaderData(col,1,k)
        col += 1    
      self.analysisGroupBoxLayout.addRow(self.view)
      
    else:
    
      m = vtk.vtkMatrix4x4()
      volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
      volumeNode.GetIJKToRASMatrix(m)
      m.Invert()
      imageData = volumeNode.GetImageData()
     
      # model and view for stats table
      self.keys = ("Label", "Intensity Average")
      self.view = qt.QTableView()
      self.view.setMinimumHeight(300)
      self.labelStats = {}
      self.labelStats['Labels'] = []
      self.view.sortingEnabled = True
      self.items = []
      self.model = qt.QStandardItemModel()
      self.view.setModel(self.model)
      self.view.verticalHeader().visible = False
      row = 0
      
      modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
      for modelNode in modelNodes.values():
        displayNode = modelNode.GetDisplayNode()
        if modelNode.GetAttribute("segmented") == "1" and displayNode.GetVisibility()==1:        
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          ijk=[0,0,0]
          ras=[0,0,0]
          total=0
          for i in range(nb):
            polyData.GetPoint(i,ras)
            k = vtk.vtkMatrix4x4()
            o = vtk.vtkMatrix4x4()
            k.SetElement(0,3,ras[0])
            k.SetElement(1,3,ras[1])
            k.SetElement(2,3,ras[2])
            k.Multiply4x4(m,k,o)
            ijk[0] = int(round(o.GetElement(0,3)))
            ijk[1] = int(round(o.GetElement(1,3)))
            ijk[2] = int(round(o.GetElement(2,3)))
            pixelValue = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
            total += pixelValue
        
          indice = total/(nb-1) 
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          phi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]*100-base[1]*100)**2)**0.5))
          theta = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
          psi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]-base[0])**2+(tip[2]-base[2])**2)**0.5))
          # print tip[0]-base[0],tip[1]-base[1],tip[2]-base[2]
          
          # result = "Needle " + self.option[int(modelNode.GetAttribute("nth"))]  +" Intensity average :" + str(indice)
          # analysisLine = qt.QLabel(result)
          # self.analysisGroupBoxLayout.addRow(analysisLine)
          
          # add an entry to the LabelStats list
          self.labelStats["Labels"].append(int(modelNode.GetAttribute("nth")))
          self.labelStats[int(modelNode.GetAttribute("nth")),"Label"] = self.option[int(modelNode.GetAttribute("nth"))]
          self.labelStats[int(modelNode.GetAttribute("nth")),"Intensity Average"] = str(indice) 
      
      for i in self.labelStats["Labels"]:
        color = qt.QColor()
        color.setRgb(self.color255[i][0],self.color255[i][1],self.color255[i][2])
        item = qt.QStandardItem()
        item.setData(color,1)
        self.model.setItem(row,0,item)
        self.items.append(item)
        col = 1
        for k in self.keys:
          item = qt.QStandardItem()
          item.setText(self.labelStats[i,k])
          self.model.setItem(row,col,item)
          self.items.append(item)
          col += 1
        row += 1

      self.view.setColumnWidth(0,30)
      self.model.setHeaderData(0,1," ")
      col = 1
      for k in self.keys:
        self.view.setColumnWidth(col,15*len(k))
        self.model.setHeaderData(col,1,k)
        col += 1 
      
      self.analysisGroupBoxLayout.addRow(self.view)
      
  def angleDeviationEvaluation(self, modelNode):
    if self.transform !=None :
      # transformation matrix
      m = self.transform.GetMatrixTransformToParent()
      m_t = vtk.vtkMatrix4x4()
      m_t.DeepCopy(m)
      
      # data from a the first planned-needle found
      modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
      stop = 1
      for modelNode in modelNodes.values():
        if modelNode.GetAttribute("planned") == "1" and stop:
          stop = 0
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          # evaluate the angle after the coordinate system transformation - used after as reference
          vtkmat = vtk.vtkMatrix4x4()              
          vtkmat.SetElement(0,3,base[0])       
          vtkmat.SetElement(1,3,base[1])
          vtkmat.SetElement(2,3,base[2])       
          m_t.Multiply4x4(m_t,vtkmat,vtkmat)
          base[0] = vtkmat.GetElement(0,3)      
          base[1] = vtkmat.GetElement(1,3)
          base[2] = vtkmat.GetElement(2,3)
          vtkmat = vtk.vtkMatrix4x4()              
          vtkmat.SetElement(0,3,tip[0])       
          vtkmat.SetElement(1,3,tip[1]) 
          vtkmat.SetElement(2,3,tip[2])      
          m_t.Multiply4x4(m_t,vtkmat,vtkmat)
          tip[0] = vtkmat.GetElement(0,3)       
          tip[1] = vtkmat.GetElement(1,3)
          tip[2] = vtkmat.GetElement(2,3)

          phi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]-base[1])**2)**0.5))
          theta1 = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
          psi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[2]-base[2])**2)**0.5))

      modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
      for modelNode in modelNodes.values():
        displayNode = modelNode.GetDisplayNode()
        if modelNode.GetAttribute("segmented") == "1" and displayNode.GetVisibility()==1:
          polyData = modelNode.GetPolyData()
          polyData.Update()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          phi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]*100-base[1]*100)**2)**0.5))
          theta = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
          psi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]-base[0])**2+(tip[2]-base[2])**2)**0.5))
          self.angleDeviation = (phi1-phi)**2+(theta1-theta)**2+(psi1-psi)**2  
  
  def positionFilteringNeedles(self):
    # remove "duplicates"
    for i in xrange(63):
      if self.base[i] != [0,0,0]:
        for j in xrange(63):
          if j != i :
            distance = (self.base[i][0] - self.base[j][0])**2 + (self.base[i][1] - self.base[j][1])**2
            # print(i,j,distance)
            if distance < 25:
              iPolyData = self.needlenode[i][1].GetPolyData()
              iNb = int(iPolyData.GetNumberOfPoints()-1)
              iPolyData.GetPoint(iNb,self.tip[i])
              jPolyData = self.needlenode[j][1].GetPolyData()
              jNb = int(iPolyData.GetNumberOfPoints()-1)
              jPolyData.GetPoint(jNb,self.tip[j])
              
              if self.tip[i][2]>=self.tip[j][2]:
                self.displaynode[j].SetVisibility(0)
              else:
                self.displaynode[i].SetVisibility(0)
                self.displaynode[i].SliceIntersectionVisibilityOff()
                slicer.mrmlScene.RemoveNode(self.needlenode[i][1])
                slicer.mrmlScene.RemoveNode(self.bentNeedleNode[i][1])
                
    self.removeDuplicatesButton.setEnabled(0)
    self.removeDuplicatesButton.setChecked(1)

  def angleFilteringNeedles(self):
    
    # transformation matrix
    m = self.transform.GetMatrixTransformToParent()
    m_t = vtk.vtkMatrix4x4()
    m_t.DeepCopy(m)
    
    # data from a the first planned-needle found
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    stop = 1
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("planned") == "1" and stop:
        stop = 0
        polyData = modelNode.GetPolyData()
        polyData.Update()
        nb = polyData.GetNumberOfPoints()
        base = [0,0,0]
        tip = [0,0,0]
        polyData.GetPoint(nb-1,tip)
        polyData.GetPoint(0,base)
        # evaluate the angle after the coordinate system transformation - used after as reference
        vtkmat = vtk.vtkMatrix4x4()              
        vtkmat.SetElement(0,3,base[0])       
        vtkmat.SetElement(1,3,base[1])
        vtkmat.SetElement(2,3,base[2])       
        m_t.Multiply4x4(m_t,vtkmat,vtkmat)
        base[0] = vtkmat.GetElement(0,3)      
        base[1] = vtkmat.GetElement(1,3)
        base[2] = vtkmat.GetElement(2,3)
        vtkmat = vtk.vtkMatrix4x4()              
        vtkmat.SetElement(0,3,tip[0])       
        vtkmat.SetElement(1,3,tip[1]) 
        vtkmat.SetElement(2,3,tip[2])      
        m_t.Multiply4x4(m_t,vtkmat,vtkmat)
        tip[0] = vtkmat.GetElement(0,3)       
        tip[1] = vtkmat.GetElement(1,3)
        tip[2] = vtkmat.GetElement(2,3)

        phi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]-base[1])**2)**0.5))
        theta1 = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
        psi1 = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[2]-base[2])**2)**0.5))
    
    # data from segmented-needles and angle evaluation
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      displayNode = modelNode.GetDisplayNode()
      if modelNode.GetAttribute("segmented") == "1":
        polyData = modelNode.GetPolyData()
        polyData.Update()
        nb = polyData.GetNumberOfPoints()
        base = [0,0,0]
        tip = [0,0,0]
        polyData.GetPoint(nb-1,tip)
        polyData.GetPoint(0,base)
        phi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]*-base[0])**2+(tip[1]*100-base[1]*100)**2)**0.5))
        theta = math.degrees(math.acos((tip[1]-base[1])/((tip[1]-base[1])**2+(tip[2]-base[2])**2)**0.5))
        psi = math.degrees(math.acos((tip[0]-base[0])/((tip[0]-base[0])**2+(tip[2]-base[2])**2)**0.5))
        angleDeviation = (phi1-phi)**2+(theta1-theta)**2+(psi1-psi)**2
        #print("diff angle:",angleDeviation)
        
        
        displayNode = modelNode.GetDisplayNode()
        i = modelNode.GetAttribute("nth")
        if angleDeviation >= self.filterValueButton.value :
          displayNode.SetVisibility(0)
          if i !=None and self.fiducialnode[int(i)]!=0:
            self.fiducialnode[int(i)].SetDisplayVisibility(0)
        else:
          displayNode.SetVisibility(1)
          if i !=None and self.fiducialnode[int(i)]!=0:
            self.fiducialnode[int(i)].SetDisplayVisibility(1)
      
      # display/hide label+needle
      nVisibility = displayNode.GetVisibility()
      
      if nVisibility == 1:
        displayNode.SliceIntersectionVisibilityOn()
      else:
        displayNode.SliceIntersectionVisibilityOff()
    
    self.addButtons()
                
  def needleSegmentation(self):
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
    
    inputVolume.SetAttribute("foldername",datetime)
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
    parameters['distanceMax'] = self.distanceMax.value
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
    xdelta= xmax - xmin
    ydelta = ymax - ymin
    self.base = [[0 for j in range(3)] for j in range(63)]
    self.tip = [[0 for j in range(3)] for j in range(63)]
    self.needlenode = [[0 for j in range(2)] for j in range(63)]
    self.bentNeedleNode = [[0 for j in range(2)] for j in range(63)]
    # self.contourNode = [[0 for j in range(2)] for j in range(63)]
    self.displaynode = [0 for j in range(63)]
    self.displaynodeB = [0 for j in range(63)]
    # self.displayContourNode = [0 for j in range(63)]
    self.fiducialnode = [0 for j in range(63)]
    k=0
    for i in xrange(63):

      pathneedle = self.foldername+'/'+str(i)+'.vtp'
      pathBentNeedle =  self.foldername+'/'+str(i)+'_bent.vtp'
      self.needlenode[i] = slicer.util.loadModel(pathneedle, True)
      self.bentNeedleNode[i] = slicer.util.loadModel(pathBentNeedle, True)


      if self.needlenode[i][0] == True and self.needlenode[i][1] != None:
        self.displaynode[i] = self.needlenode[i][1].GetDisplayNode()
        self.displaynodeB[i] = self.bentNeedleNode[i][1].GetDisplayNode()

         
        polydata = self.needlenode[i][1].GetPolyData()
        polydata.GetPoint(0,self.base[i])        
      
        self.displaynode[i].SliceIntersectionVisibilityOn()
        self.displaynodeB[i].SliceIntersectionVisibilityOn()
        bestmatch = None
        mindist = None
        for j in xrange(63):
          delta = ((self.p[0][j]-(self.base[i][0]))**2+(self.p[1][j]-self.base[i][1])**2)**(0.5)
          if delta < mindist or mindist == None:
            bestmatch = j
            mindist = delta
        if self.transform ==None :
          bestmatch = k
          k +=1
        self.displaynode[i].SetColor(self.color[bestmatch])
        self.displaynodeB[i].SetColor(self.color[bestmatch])
        self.needlenode[i][1].SetName(self.option[bestmatch]+"_segmented")
        self.bentNeedleNode[i][1].SetName(self.option[bestmatch]+"_optimized")
        self.needlenode[i][1].SetAttribute("segmented","1")
        self.bentNeedleNode[i][1].SetAttribute("optimized","1")
        self.needlenode[i][1].SetAttribute("nth",str(bestmatch))
        self.bentNeedleNode[i][1].SetAttribute("nth",str(bestmatch))
        self.needlenode[i][1].SetAttribute("needleID",self.needlenode[i][1].GetID())
        self.bentNeedleNode[i][1].SetAttribute("needleID",self.bentNeedleNode[i][1].GetID())
 
        
    
    if self.removeDuplicates.isChecked():
      self.positionFilteringNeedles()

    d = slicer.mrmlScene.GetNodeByID(outputID).GetDisplayNode()
    d.SetVisibility(0)
    
    self.__editorFrame.collapsed = 1
    
    self.addButtons()
  
  def addButtons(self):
    if self.buttonsGroupBox != None:
      self.__layout.removeWidget(self.buttonsGroupBox)
      self.buttonsGroupBox.deleteLater()
      self.buttonsGroupBox = None
    self.buttonsGroupBox = qt.QGroupBox()
    self.buttonsGroupBox.setTitle( 'Manage Needles' )
    self.__layout.addRow( self.buttonsGroupBox )
    self.buttonsGroupBoxLayout = qt.QFormLayout( self.buttonsGroupBox )
    
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("segmented") == "1":
        i = int(modelNode.GetAttribute("nth"))
        buttonDisplay = qt.QPushButton("Hide "+self.option[i])
        buttonBentDisplay = qt.QPushButton("Hide Bent "+self.option[i])
        # buttonDisplayContour = qt.QPushButton("Distance "+self.option[i])
        buttonDisplay.checkable = True
        buttonBentDisplay.checkable = True
        # buttonDisplayContour.checkable = True
        if modelNode.GetDisplayVisibility() ==0:
          buttonDisplay.setChecked(1)
          # buttonDisplayContour.setChecked(1)
        buttonDisplay.connect("clicked()", lambda who=i: self.displayNeedle(who))
        buttonBentDisplay.connect("clicked()", lambda who=i: self.displayBentNeedle(who))
        # buttonDisplayContour.connect("clicked()", functools.partial(self.displayContour,i,buttonDisplayContour.checked))
        buttonReformat = qt.QPushButton("Reformat "+self.option[i])
        buttonReformat.connect("clicked()", lambda who=i: self.reformatNeedle(who))
        widget = qt.QWidget()
        hlay = qt.QHBoxLayout(widget)
        hlay.addWidget(buttonDisplay)
        hlay.addWidget(buttonBentDisplay)
        # hlay.addWidget(buttonDisplayContour)
        hlay.addWidget(buttonReformat)
        self.buttonsGroupBoxLayout.addRow(widget)
  
  def displayBentNeedle(self,i):
    '''
    not used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    '''
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth")==str(i) and modelNode.GetAttribute("optimized")=='1' :
        displayNode = modelNode.GetModelDisplayNode()
        nVisibility = displayNode.GetVisibility()
        # print nVisibility
        if nVisibility:
          displayNode.SliceIntersectionVisibilityOff()
          displayNode.SetVisibility(0)
        else:
          displayNode.SliceIntersectionVisibilityOn()
          displayNode.SetVisibility(1)
  
  def displayNeedle(self,i):
    '''
    not used anymore. works with Yi Gao CLI module for straight needle detection + bending post-computed
    '''
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth")==str(i) and modelNode.GetAttribute("segmented")=='1' :
        displayNode = modelNode.GetModelDisplayNode()
        nVisibility = displayNode.GetVisibility()
        # print nVisibility
        if nVisibility:
          displayNode.SliceIntersectionVisibilityOff()
          displayNode.SetVisibility(0)
        else:
          displayNode.SliceIntersectionVisibilityOn()
          displayNode.SetVisibility(1)
          
          # if self.displayRadSegmentedButton.checked == 0:
            # for radNode in modelNodes.values():
              # if radNode.GetName()=='Rad'+self.option[i]+'.vtk':
                # radNode.SetDisplayVisibility(1)
          
          # if self.displayContourButton.checked == 0:
            # for radNode in modelNodes.values():
              # if radNode.GetName()==self.option[i]+'_segmented_contour':
                # radNode.SetDisplayVisibility(1)
                  
    # modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    # for modelNode in modelNodes.values():
      # if modelNode.GetAttribute("radiation") == "segmented":
        # needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        # if needleNode.GetDisplayVisibility()==0:
          # modelNode.SetDisplayVisibility(0)
    # modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    # for modelNode in modelNodes.values():
      # if modelNode.GetAttribute("contour") == "1":
        # needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        # if needleNode.GetDisplayVisibility()==0:
          # modelNode.SetDisplayVisibility(0)
      
  def showOneNeedle(self,i,visibility):
    '''
    Not used anymore. But can be usefull later
    '''
    fidname = "fid"+self.option[i]
    pNode = self.parameterNode()
    needleID = pNode.GetParameter(self.option[i]+'.vtp')
    fidID = pNode.GetParameter(fidname)    
    NeedleNode = slicer.mrmlScene.GetNodeByID(needleID)
    fiducialNode = slicer.mrmlScene.GetNodeByID(fidID)    
    
    if NeedleNode !=None:
      displayNode =NeedleNode.GetModelDisplayNode()
      nVisibility=displayNode.GetVisibility()  

      if fiducialNode == None:
        displayNode.SetVisibility(1)    
        displayNode.SetOpacity(0.9)
        polyData = NeedleNode.GetPolyData()
        polyData.Update()
        nb = int(polyData.GetNumberOfPoints()-1)
        coord = [0,0,0]
        if nb>100:
          fiducialNode = slicer.vtkMRMLAnnotationFiducialNode()
          polyData.GetPoint(nb,coord)    
          fiducialNode.SetName(self.option[i])
          fiducialNode.SetFiducialCoordinates(coord)         
          if self.transform != None:
            fiducialNode.SetAndObserveTransformNodeID(self.transform.GetID())
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
          pNode.SetParameter(fidname,fiducialNode.GetID())
          fiducialNode.SetDisplayVisibility(1)

      if visibility ==0:

        displayNode.SetVisibility(0)
        displayNode.SetSliceIntersectionVisibility(0)
        if fiducialNode!=None:
          fiducialNode.SetDisplayVisibility(0)

      else:

        displayNode.SetVisibility(1)
        displayNode.SetSliceIntersectionVisibility(1)
        if fiducialNode!=None:
          fiducialNode.SetDisplayVisibility(1)

    else:
      vtkmat = vtk.vtkMatrix4x4()
      vtkmat.DeepCopy(self.m_vtkmat)
      vtkmat.SetElement(0,3,self.m_vtkmat.GetElement(0,3)+self.p[0][i])
      vtkmat.SetElement(1,3,self.m_vtkmat.GetElement(1,3)+self.p[1][i])
      vtkmat.SetElement(2,3,self.m_vtkmat.GetElement(2,3)+(30.0-150.0)/2.0)

      TransformPolyDataFilter=vtk.vtkTransformPolyDataFilter()
      Transform=vtk.vtkTransform()        
      TransformPolyDataFilter.SetInput(self.m_polyCylinder)
      Transform.SetMatrix(vtkmat)
      TransformPolyDataFilter.SetTransform(Transform)
      TransformPolyDataFilter.Update()

      triangles=vtk.vtkTriangleFilter()
      triangles.SetInput(TransformPolyDataFilter.GetOutput())  
      self.AddModel(i,triangles.GetOutput())
      self.showOneNeedle(i,visibility)
            
  def AddModel(self,i,polyData):
    '''
    Not used. Check if can be removed
    '''
    modelNode = slicer.vtkMRMLModelNode()
    displayNode = slicer.vtkMRMLModelDisplayNode()
    storageNode = slicer.vtkMRMLModelStorageNode()
 
    fileName = self.option[i]+'.vtp'
    #print("filename:",fileName)

    mrmlScene = slicer.mrmlScene
    modelNode.SetName(fileName)  
    modelNode.SetAndObservePolyData(polyData)
    modelNode.SetAttribute("planned","1")
    
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
    if self.transform != None:
      modelNode.SetAndObserveTransformNodeID(self.transform.GetID())
    displayNode.SetColor(self.color[i])
    displayNode.SetSliceIntersectionVisibility(0)
    pNode= self.parameterNode()
    pNode.SetParameter(fileName,modelNode.GetID())
    mrmlScene.AddNode(modelNode)
    displayNode.SetVisibility(1)

  def displayRadPlanned(self):
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      displayNode = modelNode.GetDisplayNode()
      if modelNode.GetAttribute("radiation") == "planned":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode.GetDisplayVisibility()==1:
          modelNode.SetDisplayVisibility(abs(int(self.displayRadPlannedButton.checked)-1))
            
  def displayRadSegmented(self):
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("radiation") == "segmented":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility()==1:
            modelNode.SetDisplayVisibility(abs(int(self.displayRadSegmentedButton.checked)-1))
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(abs(int(self.displayRadSegmentedButton.checked)-1))
            
  def displayContour(self,i,visibility):
    # print i, visibility
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("contour") == "1" and modelNode.GetAttribute("nth")==str(i) :
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility()==1:
            modelNode.SetDisplayVisibility(visibility)
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(visibility)
            
  def displayContours(self):
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("contour") == "1":
        needleNode = slicer.mrmlScene.GetNodeByID(modelNode.GetAttribute("needleID"))
        if needleNode != None:
          if needleNode.GetDisplayVisibility()==1:
            modelNode.SetDisplayVisibility(abs(int(self.displayContourButton.checked)-1))
            d = modelNode.GetDisplayNode()
            d.SetSliceIntersectionVisibility(abs(int(self.displayContourButton.checked)-1)) 

  def displayFiducial(self):
    '''
    show labels of the needles by adding a fiducial point at the tip
    '''
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for modelNode in modelNodes.values():
      displayNode = modelNode.GetDisplayNode()
      if modelNode.GetAttribute("segmented") == "1" and modelNode.GetAttribute("nth")!=None:
        # if self.transform != None:
        if 1:
          i = int(modelNode.GetAttribute("nth"))
          if self.fiducialnode[i] == 0:    
            polyData = modelNode.GetPolyData()
            nb = int(polyData.GetNumberOfPoints()-1)
            coord = [0,0,0]
            if nb>10:
              self.fiducialnode[i] = slicer.vtkMRMLAnnotationFiducialNode()
              polyData.GetPoint(nb,coord)    
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
               self.fiducialnode[i].SetDisplayVisibility(abs(self.fiducialnode[i].GetDisplayVisibility()-1))
            if self.fiducialnode[i].GetDisplayVisibility()==1:
              self.displayFiducialButton.text = "Hide Labels on Needles"
            else:
              self.displayFiducialButton.text = "Display Labels on Needles" 

  def reformatNeedle(self,i):
    '''
    reformat the sagital view to be tangent to the needle
    '''
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    for i in range(2):  # bug from slicer? need to do it 2 times
      for modelNode in modelNodes.values():
        if modelNode.GetAttribute("nth")==str(i):
          polyData = modelNode.GetPolyData()
          nb = polyData.GetNumberOfPoints()
          base = [0,0,0]
          tip = [0,0,0]
          polyData.GetPoint(nb-1,tip)
          polyData.GetPoint(0,base)
          a,b,c = tip[0]-base[0],tip[1]-base[1],tip[2]-base[2]
          
          sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
          if sYellow ==None :
            sYellow = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")        
          reformatLogic = slicer.vtkSlicerReformatLogic()
          sYellow.SetSliceVisible(1)
          reformatLogic.SetSliceNormal(sYellow,1,-a/b,0)
          m= sYellow.GetSliceToRAS()
          m.SetElement(0,3,base[0])
          m.SetElement(1,3,base[1])
          m.SetElement(2,3,base[2])
          sYellow.Modified()

  def drawIsoSurfaces0( self ):
    '''
    used for development purposes.
    '''
    modelNodes = slicer.util.getNodes('vtkMRMLModelNode*')
    v= vtk.vtkAppendPolyData()
    
    for modelNode in modelNodes.values():
      if modelNode.GetAttribute("nth")!=None and modelNode.GetDisplayVisibility()==1 :
        v.AddInput(modelNode.GetPolyData())
       
    modeller = vtk.vtkImplicitModeller()
    modeller.SetInput(v.GetOutput())
    modeller.SetSampleDimensions(self.dim.value,self.dim.value,self.dim.value)
    modeller.SetCapping(0)
    modeller.SetAdjustBounds(self.abonds.value)
    modeller.SetProcessModeToPerVoxel() 
    modeller.SetAdjustDistance(self.adist.value/100)
    modeller.SetMaximumDistance(self.maxdist.value/100)    
    
    contourFilter = vtk.vtkContourFilter()
    contourFilter.SetNumberOfContours(self.nb.value)
    contourFilter.SetInputConnection(modeller.GetOutputPort())    
    contourFilter.ComputeNormalsOn()
    contourFilter.ComputeScalarsOn()
    contourFilter.UseScalarTreeOn()
    contourFilter.SetValue(self.contour.value,self.contourValue.value)
    contourFilter.SetValue(self.contour2.value,self.contourValue2.value)
    contourFilter.SetValue(self.contour3.value,self.contourValue3.value)
    contourFilter.SetValue(self.contour4.value,self.contourValue4.value)
    contourFilter.SetValue(self.contour5.value,self.contourValue5.value)

    isoSurface = contourFilter.GetOutput()   
    self.AddContour(isoSurface)   
  
  #----------------------------------------------------------------------------------------------
  '''
  End of the functions used with the Yi's CLI module
  '''
  #----------------------------------------------------------------------------------------------
  #----------------------------------------------------------------------------------------------
  '''
  Functions for validation study 
  '''
  #----------------------------------------------------------------------------------------------
  
  def returnTips(self):
    returnTips=[]
    modelNodes=slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
    nbNode=modelNodes.GetNumberOfItems()
    for nthNode in range(nbNode):
        # print nthNode
        node=slicer.mrmlScene.GetNthNodeByClass(nthNode,'vtkMRMLModelNode')
        if node.GetAttribute('type')=='Validation':
            polydata = node.GetPolyData()
            p,pbis=[0,0,0],[0,0,0]
            if polydata.GetNumberOfPoints()>100:
                polydata.GetPoint(0,p)
                polydata.GetPoint(int(polydata.GetNumberOfPoints()-1),pbis)
                if pbis[2]>p[2]:
                    p=pbis
                
                returnTips.append(self.ras2ijk(p))
    return returnTips

  def startValidation(self):
    tips= self.returnTips()
    # select the image node from the Red slice viewer
    m=vtk.vtkMatrix4x4()
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    spacing = volumeNode.GetSpacing()
    # chrono starts
    self.t0 = time.clock()
    for I in xrange(len(tips)):
      A=tips[I]
      colorVar = I/(len(tips))
      self.needleDetectionThread(A, imageData, colorVar,spacing)

    #print tips
    t = self.evaluate()
    print '#######################'
    print 'New Validation Results:'
    for i in range(len(t)):
        print t[i][0]

  def startValidationSCRIPT(self, volumeNodeID,tips, axialSegmentationLimit,
    radiusNeedleParameter, lenghtNeedleParameter,drawFid,nbRotatingIterations,
    distanceMax, numberOfPointsPerNeedle, stepsize,
    gradientPonderation,gaussianAttenuationChecked,sigmaValue):
    
    self.resetNeedleDetectionSCRIPT()
    
    # select the image node from the Red slice viewer
    m=vtk.vtkMatrix4x4()
    volumeNode=slicer.mrmlScene.GetNodeByID(volumeNodeID)
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    spacing = volumeNode.GetSpacing()
    # chrono starts
    self.t0 = time.clock()
    for I in xrange(len(tips)):
      A=tips[I]
      colorVar = I/(len(tips))
      self.needleDetectionThreadSCRIPT(volumeNodeID,A, axialSegmentationLimit, imageData, colorVar,spacing, radiusNeedleParameter,
    lenghtNeedleParameter,drawFid , nbRotatingIterations,
    distanceMax, numberOfPointsPerNeedle, stepsize,
    gradientPonderation,gaussianAttenuationChecked,sigmaValue)

  def needleDetectionThreadSCRIPT(self,volumeNodeID, A, axialSegmentationLimit, imageData,colorVar,spacing,radiusNeedleParameter,
    lenghtNeedleParameter,drawFid ,nbRotatingIterations,
    distanceMax, numberOfPointsPerNeedle, stepsize,
    gradientPonderation,gaussianAttenuationChecked,sigmaValue):
    '''
    From the needle tip, the algorithm looks for a direction maximizing the "needle likelihood" of a small segment in a conic region. 
    The second extremity of this segment is saved as a control point (in controlPoints), used later. 
    Then, this step is iterated, replacing the needle tip by the latest control point. 
    The height of the new conic region (stepsize) is increased as well as its base diameter (rMax) and its normal is collinear to the previous computed segment. (cf. C0) 
    NbStepsNeedle iterations give NbStepsNeedle-1 control points, the last one being used as an extremity as well as the needle tip. 
    From these NbStepsNeedle-1 control points and 2 extremities a Bezier curve is computed, approximating the needle path.
    '''
    ### length needle = distance Aijk[2]*1.1
    if axialSegmentationLimit!=None:
      lenghtNeedle = (self.ijk2rasSCRIPT(A,volumeNodeID)[2] - axialSegmentationLimit)*1.15
    else:
      lenghtNeedle = self.ijk2rasSCRIPT(A,volumeNodeID)[2]*0.9

    ### initialisation of the parameters
    self.valuesExperience=[radiusNeedleParameter,lenghtNeedleParameter,
    distanceMax, numberOfPointsPerNeedle, nbRotatingIterations,stepsize,
    gradientPonderation,gaussianAttenuationChecked,sigmaValue]
    ijk = [0,0,0]
    bestPoint = [0,0,0]
    # lenghtNeedle = lenghtNeedleParameter/float(spacing[2])
    rMax = distanceMax/float(spacing[0])
    NbStepsNeedle = numberOfPointsPerNeedle-1
    nbRotatingStep = nbRotatingIterations

    dims=[0,0,0]
    imageData.GetDimensions(dims)
    pixelValue = numpy.zeros(shape=(dims[0],dims[1],dims[2]))
    # difference: evaluate difference in average intensity between to position : new one and old one (oldtotal)
    difference = 0
    oldtotal = 0
    A0=A
    controlPoints = []
    controlPointsIJK = []
    controlPoints.append(self.ijk2rasSCRIPT(A,volumeNodeID))
    controlPointsIJK.append(A)
    bestControlPoints = []
    bestControlPoints.append(self.ijk2rasSCRIPT(A,volumeNodeID))
    for step in range(0,NbStepsNeedle+2):
      if step>0:
        norm= (   (A[0]-tip0[0])**2   
                 +(A[1]-tip0[1])**2
                 +(A[2]-tip0[2])**2  )**(0.5)
        lengthSegmented=+norm

      #step 0
      #------------------------------------------------------------------------------
      if step==0:
        L = 20/float(spacing[2])
        C0 = [A[0],A[1],A[2]- L]
        rMax = distanceMax/float(spacing[0])
        rIter = rMax
        tIter = int(round(L))
        


      #step 1,2,...
      #------------------------------------------------------------------------------
      else:
        
        stepSize = max(self.stepSize(step,NbStepsNeedle+1)*lenghtNeedle,stepsize/float(spacing[2]))
        # stepSize = min (A[2],stepSize)

        C0 = [  2*A[0]-tip0[0],
                2*A[1]-tip0[1],
                A[2]-stepSize]
        rMax = max(stepSize,distanceMax/float(spacing[0]))
        # rIter = max(int(stepsize/(2))+5,nbRadiusIterations.value)
        rIter = int(max(15,min(20,int(rMax/float(spacing[0])))))
        tIter = stepSize
        
      estimator = 0
      minEstimator = 0  

      #radius variation
      for R in range(rIter+1):
        r=R*(rMax/float(rIter))
        
        ### angle variation from 0 to 360
        for thetaStep in xrange(nbRotatingStep ):
          angleInDegree = (thetaStep*360)/float(nbRotatingStep)
          theta = math.radians(angleInDegree)

          C = [   C0[0]+r*(math.cos(theta)),
                  C0[1]+r*(math.sin(theta)),
                  C0[2]]

          total = 0
          M=[[0,0,0] for i in xrange(tIter+1)]
          
         
          # calculates tIter = number of points per segment 
          for t in xrange(tIter+1):
            tt = t/float(tIter)
            # x,y,z coordinates
            for i in range(3):
              M[t][i] = (1-tt)*A[i] + tt*C[i]
              ijk[i]=int(round(M[t][i]))
              
            # first, test if points are in the image space 
            if ijk[0]<dims[0] and ijk[0]>0 and  ijk[1]<dims[1] and ijk[1]>0 and ijk[2]<dims[2] and ijk[2]>0:
              center=imageData.GetScalarComponentAsDouble(ijk[0], ijk[1], ijk[2], 0)
              total += center
              if 1==1:
                radiusNeedle = int(round(radiusNeedleParameter/float(spacing[0])))
                radiusNeedleCorner = int(round((radiusNeedleParameter/float(spacing[0])/1.414)))
                g1 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedle, ijk[1], ijk[2], 0)
                g2 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedle, ijk[1], ijk[2], 0)
                g3 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]+radiusNeedle, ijk[2], 0)
                g4 = imageData.GetScalarComponentAsDouble(ijk[0], ijk[1]-radiusNeedle, ijk[2], 0)
                g5 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)                    
                g6 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                g7 = imageData.GetScalarComponentAsDouble(ijk[0]-radiusNeedleCorner, ijk[1]+radiusNeedleCorner, ijk[2], 0)
                g8 = imageData.GetScalarComponentAsDouble(ijk[0]+radiusNeedleCorner, ijk[1]-radiusNeedleCorner, ijk[2], 0)
                total += 8*center - ((g1+g2+g3+g4+g5+g6+g7+g8)/8)*gradientPonderation
              
          if R==0:
            initialIntensity = total
            estimator = total
            
          if gaussianAttenuationChecked==1 and step>=2 :
            if tip0[2]-A[2]!=0:
            
                stepSize=(A[2] - C0[2])
                K=stepSize/float(tip0[2]-A[2])

                X = [       A[0] + K * (A[0]-tip0[0]),
                            A[1] + K * (A[1]-tip0[1]),
                            A[2] + K * (A[2]-tip0[2]) ]

                rgauss = (  (C[0]-X[0])**2 
                            +(C[1]-X[1])**2
                            +(C[2]-X[2])**2 )**0.5

                gaussianAttenuation = math.exp(-(rgauss/float(rMax))**2/float((2*(sigmaValue/float(10))**2)))   # 1 for x=0, 0.2 for x=5
                estimator = (total)*gaussianAttenuation
            else:
                estimator = total


          else:
            estimator = (total)
       
          if estimator<initialIntensity:

            if estimator<minEstimator or minEstimator == 0:
              minEstimator=estimator
              if minEstimator!=0:  
                bestPoint=C
        
           
      tip0=A
      if bestPoint==[0,0,0]:
        A=C0
      elif bestPoint!=tip0: 
        A=bestPoint
 
      if A[2]<axialSegmentationLimit:
        
        asl=axialSegmentationLimit
        l = (A[2]-asl)/float(tip0[2]-A[2])

        A=[ A[0] - l*(tip0[0]-A[0]),
            A[1] - l*(tip0[1]-A[1]),
            A[2] - l*(tip0[2]-A[2])]

      controlPoints.append(self.ijk2rasSCRIPT(A,volumeNodeID))
      controlPointsIJK.append(A)
      if drawFid==1:
        fiducial = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
        fiducial.Initialize(slicer.mrmlScene)
        fiducial.SetName('.')
        fiducial.SetFiducialCoordinates(controlPoints[step+1])

      if A[2]<=axialSegmentationLimit:
        break

    self.addNeedleToSceneSCRIPT(controlPoints,colorVar)


  def addNeedleToSceneSCRIPT(self,controlPoint,colorVar, needleType='Detection'): 
    '''
    Create a model of the needle from its equation (Beziers curve fitting the control points)
    '''
    # initialisation
    # print controlPoint
    label=None
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
    polyData.SetPolys( polygons )
    idArray = polygons.GetData()
    idArray.Reset()
    idArray.InsertNextTuple1(0)
    nbEvaluationPoints=50
    n = len(controlPoint)-1
    Q=[[0,0,0] for t in range(nbEvaluationPoints+1)]
    # start calculation
    for t in range(nbEvaluationPoints):
      tt = float(t)/(1*nbEvaluationPoints)
      for j in range(3):
        for i in range(n+1):
          Q[t][j]+=self.binomial(n,i)*(1-tt)**(n-i)*tt**i*controlPoint[i][j]
          
      pointIndex = points.InsertNextPoint(*Q[t])
      linesIDArray.InsertNextTuple1(pointIndex)
      linesIDArray.SetTuple1( 0, linesIDArray.GetNumberOfTuples() - 1 )
      lines.SetNumberOfCells(1)
    ### Create model node
    model = slicer.vtkMRMLModelNode()
    model.SetScene(scene)
    model.SetAndObservePolyData(polyData)
    ### Create display node
    modelDisplay = slicer.vtkMRMLModelDisplayNode()
    # functions below are not used anymore. can be removed
    # if self.round==1: 
    #   modelDisplay.SetColor(1,1-colorVar,colorVar) # yellow to magenta
    # elif self.round==2:
    #   modelDisplay.SetColor(colorVar,1,1) # cyan
    # elif self.round==3:
    #   modelDisplay.SetColor(1,0.5+colorVar/2,1) # 
    # elif self.round==4:
    #   modelDisplay.SetColor(0.5+colorVar/2,1,0.5+colorVar/2) #
    # else:
    #   modelDisplay.SetColor(random.randrange(0,10,1)/(10),random.randrange(0,10,1)/(10),random.randrange(0,10,1)/(10))

    modelDisplay.SetScene(scene)
    scene.AddNode(modelDisplay)
    model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
    ### Add to scene
    modelDisplay.SetInputPolyData(model.GetPolyData())
    scene.AddNode(model)
    ###Create Tube around the line
    tube=vtk.vtkTubeFilter()
    polyData = model.GetPolyData()
    tube.SetInput(polyData)
    tube.SetRadius(1)
    tube.SetNumberOfSides(50)
    tube.Update()
    model.SetAndObservePolyData(tube.GetOutput())
    model.GetDisplayNode().SliceIntersectionVisibilityOn()
    if needleType=='Validation':
      model.SetName('manual-seg_'+str(colorVar))
    else:
      model.SetName('python-catch-round_'+str(self.round)+'-ID-'+str(model.GetID()))
    model.SetAttribute('type',needleType)
    
    # evaluate and print the processing time
    processingTime = time.clock()-self.t0
    # print processingTime

    # if registration has been done, find the label for the needle

    if needleType=='Validation':
      nth = colorVar
      # modelDisplay.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
      model.SetAttribute("nth",str(nth)) 
    else:
      nth = model.GetID().strip('vtkMRMLModelNode')
      # modelDisplay.SetColor(self.color[int(nth)][0],self.color[int(nth)][1],self.color[int(nth)][2])
      model.SetAttribute("nth",str(nth))

    self.processingTime = time.clock()-self.t0

  def resetNeedleDetectionSCRIPT(self):
    '''
    Reset the needle detection to completely start over.
    '''
    while slicer.util.getNodes('python-catch*') != {}:
      nodes = slicer.util.getNodes('python-catch*')
      for node in nodes.values():
        slicer.mrmlScene.RemoveNode(node)
      self.previousValues=[[0,0,0]]


  def ijk2rasSCRIPT(self,A,volumeNodeID):
    '''
    Convert IJK coordinates to RAS coordinates. The transformation matrix is the one 
    of the active volume on the red slice
    '''
    m=vtk.vtkMatrix4x4()
    volumeNode=slicer.mrmlScene.GetNodeByID(volumeNodeID)
    volumeNode.GetIJKToRASMatrix(m)
    imageData = volumeNode.GetImageData()
    ras=[0,0,0]
    k = vtk.vtkMatrix4x4()
    o = vtk.vtkMatrix4x4()
    k.SetElement(0,3,A[0])
    k.SetElement(1,3,A[1])
    k.SetElement(2,3,A[2])
    k.Multiply4x4(m,k,o)
    ras[0] = o.GetElement(0,3)
    ras[1] = o.GetElement(1,3)
    ras[2] = o.GetElement(2,3)
    return ras

  def selectCurrentAxialSlice(self):
    '''
    Get the K (of IJK) value of the current axial slice. 
    Used to define the slice containing the template
    '''
    if self.fiducialNode != None:
        slicer.mrmlScene.RemoveNode(self.fiducialNode)

    s           =   slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetSliceNode()
    offSet      =   s.GetSliceOffset()
    rasVector   =   [0,0,offSet]
    self.templateSliceButton.text = "Select Current Axial Slice as seg. limit (current: "+str(offSet)+")"

    self.axialSegmentationLimit = int(round(self.ras2ijk(rasVector)[2]))

    self.fiducialNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    self.fiducialNode.Initialize(slicer.mrmlScene)
    self.fiducialNode.SetName('template slice position')        
    self.fiducialNode.SetFiducialCoordinates(rasVector)
    fd=self.fiducialNode.GetDisplayNode()
    fd.SetVisibility(1)
    fd.SetColor([0,1,0])
    
    #print self.axialSegmentationLimit


  def exportEvaluation(self,results,url):
    self.valuesExperience=[ self.radiusNeedleParameter.value,
                            self.lenghtNeedleParameter.value,
                            self.distanceMax.value,
                            self.numberOfPointsPerNeedle.value, 
                            self.nbRotatingIterations.value,
                            self.stepsize.value,
                            self.gradientPonderation.value,
                            self.gaussianAttenuationChecked.value,
                            self.sigmaValue.value]
    myfile = open(url, 'a')
    wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
    results.append(self.valuesExperience)
    wr.writerow(results)

  def hausdorffDistance2(self,id1,id2):
      node1 = slicer.mrmlScene.GetNodeByID(id1)
      polydata1=node1.GetPolyData()
      node2 = slicer.mrmlScene.GetNodeByID(id2)
      polydata2=node2.GetPolyData()
      nb1 = polydata1.GetNumberOfPoints()
      nb2 = polydata2.GetNumberOfPoints()
      minimum=None
      maximum=None
      JJ,jj=None,None
      II,ii=None,None
      pt1=[0,0,0]
      pt2=[0,0,0]
      polydata1.GetPoint(1,pt1)
      polydata1.GetPoint(nb1-1,pt2)
      minVal1=min(pt1[2],pt2[2])
      maxVal1=max(pt1[2],pt2[2])
      pt1=[0,0,0]
      pt2=[0,0,0]
      pt1b,pt2b=None,None
      polydata2.GetPoint(1,pt1)
      polydata2.GetPoint(nb2-1,pt2)
      minVal2 = min(pt1[2],pt2[2])
      maxVal2 = max(pt1[2],pt2[2])
      valueBase=max(minVal1,minVal2)
      valueTip=min(maxVal1,maxVal2)

      # truncate polydatas
      truncatedPolydata1 = self.clipPolyData(node1,valueBase)
      truncatedPolydata2 = self.clipPolyData(node2,valueBase)

      cellId=vtk.mutable(1)
      subid=vtk.mutable(1)
      dist=vtk.mutable(1)
      cl2=vtk.vtkCellLocator()
      cl2.SetDataSet(truncatedPolydata2)
      cl2.BuildLocator()
      # Hausforff 1 -> 2
      minima=[]
      for i in range(int(nb1/float(10))):
        pt=[0,0,0]
        polydata1.GetPoint(10*i,pt)
        closest=[0,0,0]
        cl2.FindClosestPoint(pt,closest,cellId,subid,dist)
        if abs(closest[2]-pt[2])<=1:
          minima.append(self.distance(pt,closest))
        else:
            minima.append(0)
      hausdorff12 = max(minima)
      
      # Hausforff 2 -> 1
      minima=[]
      cl1=vtk.vtkCellLocator()
      cl1.SetDataSet(truncatedPolydata1)
      cl1.BuildLocator()
      for i in range(int(nb2/float(10))):
        pt=[0,0,0]
        polydata2.GetPoint(10*i,pt)
        closest=[0,0,0]
        cl1.FindClosestPoint(pt,closest,cellId,subid,dist)
        if abs(closest[2]-pt[2])<=1:
          minima.append(self.distance(pt,closest))
        else:
            minima.append(0)
      hausdorff21 = max(minima)
      return max(hausdorff12,hausdorff21)

  def evaluate(self):
      result=self.needleMatching()
      HD=[]
      for i in range(len(result)):
        val=self.hausdorffDistance2(result[i][1],result[i][2])
        results = [float(val),int(result[i][1].strip('vtkMRMLModelNode')),int(result[i][2].strip('vtkMRMLModelNode'))]
        HD.append(results)
      return np.array(HD).astype(np.longdouble)

  def distTip(self,id1,id2):
      node = slicer.mrmlScene.GetNodeByID('vtkMRMLModelNode'+str(id1))
      polydata=node.GetPolyData()
      node2 = slicer.mrmlScene.GetNodeByID('vtkMRMLModelNode'+str(id2))
      polydata2=node2.GetPolyData()
      p,pbis=[0,0,0],[0,0,0]
      p2=[0,0,0]
      p2bis=[0,0,0]
      axialDistance=[]
      for i in range(100):
          polydata.GetPoint(i,p)
          polydata.GetPoint(2499-i,pbis)
          if pbis[2]>p[2]:
            p=pbis
          polydata2.GetPoint(2499-i,p2)
          polydata2.GetPoint(i,p2bis)
          if p2bis[2]>p2[2]:
            p2=p2bis
          axialDistance.append((( p2[0]-p[0] )**2 +  ( p2[1]-p[1] )**2)**0.5)
      return min(axialDistance)


  def needleMatching(self):
      modelNodes=slicer.mrmlScene.GetNodesByClass('vtkMRMLModelNode')
      nbNode=modelNodes.GetNumberOfItems()
      result=[]
      found=[]
      #print nbNode
      for nthNode in range(nbNode):
        node=slicer.mrmlScene.GetNthNodeByClass(nthNode,'vtkMRMLModelNode')
        if node.GetID() not in found and node.GetAttribute('type')!='Validation':
          dist=[]
          polydata = node.GetPolyData()
          if polydata!=None:
            bounds = polydata.GetBounds()
            for nthNode2 in range(nbNode):
              node2=slicer.mrmlScene.GetNthNodeByClass(nthNode2,'vtkMRMLModelNode')
              if node2.GetID() not in found and node2.GetAttribute('type')=='Validation':
                polydata2 = node2.GetPolyData()
                if polydata2!=None and polydata2.GetNumberOfPoints()>100 and polydata.GetNumberOfPoints()>100:
                  bounds2 = polydata2.GetBounds()
                  tot=0
                  p,pbis=[0,0,0],[0,0,0]
                  p2=[0,0,0]
                  p2bis=[0,0,0]
                  polydata.GetPoint(0,p)
                  polydata.GetPoint(0,pbis)
                  polydata2.GetPoint(2499,p2)
                  polydata2.GetPoint(0,p2bis)
                  # tot=min(( p[0]-p2[0] )**2 +  ( p[1]-p2[1] )**2,  ( p[0]-p2bis[0] )**2 +  ( p[1]-p2bis[1] )**2 , (pbis[0]-p2[0] )**2 +  ( pbis[1]-p2[1] )**2 , (pbis[0]-p2bis[0] )**2 +  ( pbis[1]-p2bis[1] )**2)
                  # axialDistance=(tot)**(0.5)
                  axialDistance=self.distTip( int(node.GetID().strip('vtkMRMLModelNode')) , int(node2.GetID().strip('vtkMRMLModelNode')))
                  # axialDistance=hausdorffDistance(node.GetID(), node2.GetID())
                  dist.append([axialDistance,node2.GetID()])
                  # print axialDistance
                  
            if dist!=[]:
              match=[min(dist)[0],min(dist)[1],node.GetID()]
              result.append(match)
              found.append(min(dist)[1])
              found.append(node.GetID()) 
              node.GetDisplayNode().SetSliceIntersectionVisibility(1)
      # print result
      return result

  def distance(self,pt1,pt2):
    d = ( (  float(pt1[0]) - float(pt2[0])  )**2 + (  float(pt1[1]) - float(pt2[1])  )**2 + (  float(pt1[2]) - float(pt2[2])  )**2 )**0.5
    return d


  def addManualTip(self,A):
    self.fiducialNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLAnnotationFiducialNode')
    self.fiducialNode.Initialize(slicer.mrmlScene)
    self.fiducialNode.SetName('tip')        
    self.fiducialNode.SetFiducialCoordinates(A)
    fd=self.fiducialNode.GetDisplayNode()
    fd.SetVisibility(1)
    fd.SetColor([0,1,0])

  def distanceTwoPoints(self,A,B):
    # used in addNeedleToScene
    length = ( (A[0]-B[0])**2 + (A[1]-B[1])**2 + (A[2]-B[2])**2 ) ** 0.5
    return length
  
  def clipPolyData(self,node,value,visible=0):
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
    clipper.SetInput(node.GetPolyData())
    clipper.SetClipFunction(plane)
    clipper.GenerateClipScalarsOn()
    clipper.GenerateClippedOutputOn()
    clipper.SetValue(value)
    polyData = clipper.GetOutput()
    if 1==1:
        scene   =   slicer.mrmlScene
        model = slicer.vtkMRMLModelNode()
        model.SetScene(scene)
        model.SetAndObservePolyData(polyData)
        ### Create display node
        modelDisplay = slicer.vtkMRMLModelDisplayNode()
        modelDisplay.SetScene(scene)
        scene.AddNode(modelDisplay)
        model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
        ### Add to scene
        modelDisplay.SetInputPolyData(model.GetPolyData())
        scene.AddNode(model)
    if visible!=1:
        scene.RemoveNode(model)

    return polyData

  def setWL(self,dn,w,l):
    dn.SetWindow(w)
    dn.SetLevel(l)




