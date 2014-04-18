from __main__ import qt, ctk, slicer
import os
import glob
from NFStep import *
from Helper import *
import DICOMLib
import PythonQt

class NFLoadModelStep( NFStep ) :

  def __init__( self, stepid ):
    self.initialize( stepid )
    self.setName( '3. Load the CAD Model of the applicator' )
    self.setDescription( 'Load the CAD Models.' )
    self.__parent = super( NFLoadModelStep, self )
    self.loadTemplateButton = None

  def createUserInterface( self ):
    self.__layout = self.__parent.createUserInterface()

    baselineScanLabel = qt.QLabel( 'CT or MR scan:' )
    self.__baselineVolumeSelector = slicer.qMRMLNodeComboBox()
    self.__baselineVolumeSelector.objectName = 'baselineVolumeSelector'
    self.__baselineVolumeSelector.toolTip = "Choose the baseline scan"
    self.__baselineVolumeSelector.nodeTypes = ['vtkMRMLScalarVolumeNode']
    self.__baselineVolumeSelector.setMRMLScene(slicer.mrmlScene)
    self.__baselineVolumeSelector.noneEnabled = False
    self.__baselineVolumeSelector.addEnabled = False
    self.__baselineVolumeSelector.removeEnabled = False
    self.__layout.connect('mrmlSceneChanged(vtkMRMLScene*)',
                        self.__baselineVolumeSelector, 'setMRMLScene(vtkMRMLScene*)')

	  #Load Template Button 
    self.loadTemplateButton = qt.QPushButton('Load template')
    self.__layout.addRow(self.loadTemplateButton)
    self.loadTemplateButton.connect('clicked()', self.loadTemplate)

	  #Load Scan Button
    self.__fileFrame = ctk.ctkCollapsibleButton()
    self.__fileFrame.text = "NRRD File Input"
    self.__fileFrame.collapsed = 1
    fileFrame = qt.QFormLayout(self.__fileFrame)
    self.__layout.addRow(self.__fileFrame)
   
    loadDataButton = qt.QPushButton('Load Scan')
    loadDataButton.connect('clicked()', self.loadData)
    fileFrame.addRow(loadDataButton)

    # Sample Data Button
    sampleDATA = qt.QPushButton('Download Sample Data')
    sampleDATA.connect('clicked()',self.downloadPhantom)
    fileFrame.addRow(sampleDATA)
    
    # Sample Data Status
    self.log = qt.QTextEdit()
    self.log.readOnly = True
    self.__fileFrame.layout().addRow(self.log)
    self.logMessage('<p>Status: <i>Idle</i>\n')

    self.__layout.addRow( baselineScanLabel, self.__baselineVolumeSelector )

    qt.QTimer.singleShot(0, self.killButton)
      
  def killButton(self):
    # hide useless button
    bl = slicer.util.findChildren(text='NeedleSegmentation')
    if len(bl):
      bl[0].hide()


  def loadData(self):
    slicer.util.openAddDataDialog()

  def validate( self, desiredBranchId ):
    '''
    '''
    pNode = self.parameterNode()

    if pNode.GetParameter('skip') != '1':
      self.__parent.validate( desiredBranchId )
      # check here that the selectors are not empty
      
      baseline = self.__baselineVolumeSelector.currentNode()
      template=slicer.util.getNode('Template')
      obturator = slicer.util.getNode('Obturator_reg')

      df = template.GetDisplayNode()
      do = obturator.GetDisplayNode()
      df.SetSliceIntersectionVisibility(0)
      do.SetSliceIntersectionVisibility(0)
      #print template.GetID()

      if baseline != None and template != None and obturator != None:
        baselineID = baseline.GetID()
        templateID = template.GetID()
        obturatorID = obturator.GetID()
      
        pNode = self.parameterNode()
        pNode.SetParameter('baselineVolumeID', baselineID)
        pNode.SetParameter('templateID', templateID)
        pNode.SetParameter('obturatorID', obturatorID)

        self.__parent.validate( desiredBranchId )
        self.__parent.validationSucceeded(desiredBranchId)
       
      else:
        self.__parent.validationFailed(desiredBranchId, 'Error','Please select both Template and scan/DICOM Volume!')
    
    else:
      self.__parent.validate( desiredBranchId )
      self.__parent.validationSucceeded(desiredBranchId)
  
  def onEntry(self,comingFrom,transitionType):
  
    super(NFLoadModelStep, self).onEntry(comingFrom, transitionType)
    # setup the interface
    pNode = self.parameterNode()
    pNode.SetParameter('currentStep', self.stepid)
    if pNode.GetParameter('skip') != '1':
      applicator  = pNode.GetParameter('Template')
      if applicator == "4points":
        self.loadTemplate(4)
      if applicator == "3points":
        self.loadTemplate(3)
    elif pNode.GetParameter('skip')=='1':
      self.workflow().goForward() # 4      
      
  def onExit(self, goingTo, transitionType):
   
    pNode= self.parameterNode()
    #print pNode
    if pNode.GetParameter('skip') != '1':
      self.doStepProcessing()
    #error checking
    if goingTo.id() != 'SelectApplicator' and goingTo.id() != 'FirstRegistration':
      return
    super(NFLoadModelStep, self).onExit(goingTo, transitionType) 

  def updateWidgetFromParameters(self, parameterNode):
    baselineVolumeID = parameterNode.GetParameter('baselineVolumeID')
    if baselineVolumeID != None:
      self.__baselineVolumeSelector.setCurrentNode(slicer.mrmlScene.GetNodeByID(baselineVolumeID))

  def doStepProcessing(self):

    # calculate the transform to align the ROI in the next step with the
    # baseline volume
    pNode = self.parameterNode()

    baselineVolume = slicer.mrmlScene.GetNodeByID(pNode.GetParameter('baselineVolumeID'))
    template = slicer.mrmlScene.GetNodeByID(pNode.GetParameter('templateID'))
   
    roiTransformID = pNode.GetParameter('roiTransformID')
    roiTransformNode = None
    
    if roiTransformID != '':
      roiTransformNode = slicer.mrmlScene.GetNodeByID(roiTransformID)
    else:
      roiTransformNode = slicer.mrmlScene.CreateNodeByClass('vtkMRMLLinearTransformNode')
      slicer.mrmlScene.AddNode(roiTransformNode)
      pNode.SetParameter('roiTransformID', roiTransformNode.GetID())

    if template != None:
      dm = vtk.vtkMatrix4x4()
      bounds = [0,0,0,0,0,0]
      template.GetRASBounds(bounds)
      dm.SetElement(0,3,(bounds[0]+bounds[1])/float(2))
      dm.SetElement(1,3,(bounds[2]+bounds[3])/float(2))
      dm.SetElement(2,3,(bounds[4]+bounds[5])/float(2))
      dm.SetElement(0,0,abs(dm.GetElement(0,0)))
      dm.SetElement(1,1,abs(dm.GetElement(1,1)))
      dm.SetElement(2,2,abs(dm.GetElement(2,2)))
      roiTransformNode.SetAndObserveMatrixTransformToParent(dm)     

  def loadTemplate(self,nb):
    '''
    Load scene with template, obturator and landmarks
    '''
    pNode = self.parameterNode()
    alreadyloaded = pNode.GetParameter("Template-loaded")
    if alreadyloaded != "1":
      if nb == 3:
        pathToScene = slicer.modules.needlefinder.path.replace("NeedleFinder/NeedleFinder.py","NeedleFinder/Resources/Template/3points/Template.mrml")
      elif nb ==4:
        pathToScene = slicer.modules.needlefinder.path.replace("NeedleFinder/NeedleFinder.py","NeedleFinder/Resources/Template/4points/Template.mrml")

      # slicer.util.loadScene( pathToScene, True)
      slicer.util.loadScene( pathToScene)
      self.loadTemplateButton.setEnabled(0)
      pNode.SetParameter("Template-loaded","1")

  #------------------------------------------------------------------------------------
  '''Download Sample Data'''
  #------------------------------------------------------------------------------------
  def logMessage(self,message):
    self.log.insertHtml(message)
    self.log.insertPlainText('\n')
    self.log.ensureCursorVisible()
    self.log.repaint()
    slicer.app.processEvents(qt.QEventLoop.ExcludeUserInputEvents)

  def downloadPhantom(self):
    filePath = self.downloadFileIntoCache('http://slicer.kitware.com/midas3/download?items=11319', 'phantomGYN.nrrd')
    return self.loadVolume(filePath, 'phantomGYN')

  def downloadFileIntoCache(self, uri, name):
    destFolderPath = slicer.mrmlScene.GetCacheManager().GetRemoteCacheDirectory()
    return self.downloadFile(uri, destFolderPath, name)

  def humanFormatSize(self,size):
    """ from http://stackoverflow.com/questions/1094841/reusable-library-to-get-human-readable-version-of-file-size"""
    for x in ['bytes','KB','MB','GB']:
      if size < 1024.0 and size > -1024.0:
        return "%3.1f%s" % (size, x)
      size /= 1024.0
    return "%3.1f%s" % (size, 'TB')

  def reportHook(self,blocksSoFar,blockSize,totalSize):
    percent = int((100. * blocksSoFar * blockSize) / totalSize)
    if percent == 100 or (percent - self.downloadPercent >= 10):
      humanSizeSoFar = self.humanFormatSize(blocksSoFar * blockSize)
      humanSizeTotal = self.humanFormatSize(totalSize)
      self.logMessage('<i>Downloaded %s (%d%% of %s)...</i>' % (humanSizeSoFar, percent, humanSizeTotal))
      self.downloadPercent = percent

  def downloadFile(self, uri, destFolderPath, name):
    filePath = destFolderPath + '/' + name
    if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
      import urllib
      self.logMessage('<b>Requesting download</b> <i>%s</i> from %s...\n' % (name, uri))
      # add a progress bar
      self.downloadPercent = 0
      try:
        urllib.urlretrieve(uri, filePath, self.reportHook)
        self.logMessage('<b>Download finished</b>')
      except IOError as e:
        self.logMessage('<b><font color="red">\tDownload failed: %s</font></b>' % e)
    else:
      self.logMessage('<b>File already exists in cache - reusing it.</b>')
    return filePath

  def loadVolume(self, uri, name):
    self.logMessage('<b>Requesting load</b> <i>%s</i> from %s...\n' % (name, uri))
    success, volumeNode = slicer.util.loadVolume(uri, properties = {'name' : name}, returnNode=True)
    if success:
      self.logMessage('<b>Load finished</b>\n')
    else:
      self.logMessage('<b><font color="red">\tLoad failed!</font></b>\n')
    return volumeNode
      