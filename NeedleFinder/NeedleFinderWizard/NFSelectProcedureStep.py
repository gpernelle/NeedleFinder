from __main__ import qt, ctk
import os.path, time
from NFStep import *
from Helper import *


class NFSelectProcedureStep( NFStep ) :

  def __init__( self, stepid ):
    self.skip = 1
    self.initialize( stepid )
    self.setName( '1. Select the Procedure' )
    file = slicer.modules.needlefinder.path
    builddate = time.gmtime(os.path.getmtime(file))
    creationdate = int(12*365.25 + 188)# 07/07/2012
    todaydate = int((builddate.tm_year - 2000)*365.25+builddate.tm_yday)
    versionnumber = todaydate - creationdate
    self.version = str(versionnumber)
    self.setDescription( 'NeedleFinder v1.0.' + self.version + '       Last Modified: ' + time.ctime(os.path.getmtime(file)) )
    
    self.__parent = super( NFSelectProcedureStep, self )

  def createUserInterface( self ):
    '''
    '''
    # self.buttonBoxHints = self.ButtonBoxHidden

    self.__layout = self.__parent.createUserInterface()
    
    # self.templateButton = qt.QRadioButton("Start Registration")
    # self.templateButton.setChecked(1)
    # self.noTemplateButton = qt.QRadioButton("Switch directly to Needle Segmentation")  
    # self.__layout.addRow(self.templateButton)
    # self.__layout.addRow(self.noTemplateButton)


    chooseModeLabel = qt.QLabel( 'Choose Mode' )
    chooseModeLabel.setFont( self.getBoldFont() )
    self.__layout.addRow( chooseModeLabel )

    self.__buttonBox = qt.QDialogButtonBox()
    self.simpleButton = self.__buttonBox.addButton( self.__buttonBox.Discard )
    self.simpleButton.setIcon( qt.QIcon() )
    self.simpleButton.text = "Registration"
    self.simpleButton.checkable = True
    self.simpleButton.toolTip = "Click to start the registration."
    self.advancedButton = self.__buttonBox.addButton( self.__buttonBox.Apply )
    self.advancedButton.setIcon( qt.QIcon() )
    self.advancedButton.checkable = True
    self.advancedButton.text = "Needle Segmentation"
    self.advancedButton.toolTip = "Click to start the needle segmentation."
    self.__layout.addWidget( self.__buttonBox )
  
    # connect the simple and advanced buttons
    self.simpleButton.connect( 'clicked()', self.goSimple )
    self.advancedButton.connect( 'clicked()', self.goAdvanced )

    qt.QTimer.singleShot(0, self.killButton)
      
  def killButton(self):
    # hide useless button
    bl = slicer.util.findChildren(text='NeedleSegmentation')
    if len(bl):
      bl[0].hide()

  def onEntry(self, comingFrom, transitionType):

    super(NFSelectProcedureStep, self).onEntry(comingFrom, transitionType)
    pNode = self.parameterNode()
    pNode.SetParameter('currentStep', self.stepid)
    pNode.SetParameter('skip', '0')
    #print pNode
    

  def onExit(self, goingTo, transitionType):
  
    pNode = self.parameterNode()
    if goingTo.id() != 'SelectApplicator' and goingTo.id() != 'NeedleSegmentation':
      return
    
    if self.skip==1:
      pNode.SetParameter('skip', '1')
      self.workflow().goForward() # 2   
    else:
      pNode.SetParameter('skip', '0')
      super(NFSelectProcedureStep, self).onExit(goingTo, transitionType)   

  def validate( self, desiredBranchId ):
    '''
    '''
    self.__parent.validate( desiredBranchId )    
    self.__parent.validationSucceeded(desiredBranchId)

  def goSimple( self ):
    '''
    '''
    self.advancedButton.checked = False
    self.skip = 0
    #print 'start registration'
    # workflow = self.workflow()
    # if not workflow:
    #   Helper.Error( "No valid workflow found!" )
    #   return False

    # if self.workflow().isRunning:
    #    workflow.goForward( 'RegistrationMode' )
    #    #print 'goForward'
    # else:
    #    workflow.start()
    #    Helper.Info("Please press Registration button again")

  def goAdvanced( self ):
    '''
    '''
    self.simpleButton.checked = False
    self.skip = 1
    #print 'go to needle segmentation'
    # workflow = self.workflow()
    # if not workflow:
    #   Helper.Error( "No valid workflow found!" )
    #   return False

    # # When the Reset button is pressed in the Label Statistics 
    # # then the workflow is stopped  and started again - jumping to this panel 
    # # for some reason the workflow is then stopped again - I do not know why - testing it on entry everything works fine 
    # # just press the button twice and everything works fine 
    # if self.workflow().isRunning:
    #    workflow.goForward( 'NeedleSegmentationMode' )
    # else:
    #    workflow.start()
    #    Helper.Info("Please press Needle Segmentation button again")
