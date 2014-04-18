from __main__ import qt, ctk, slicer

from NFStep import *
from Helper import *
import PythonQt

class NFSelectApplicatorStep( NFStep ) :

  def __init__( self, stepid ):
    self.initialize( stepid )
    self.setName( '2. Choose Applicator' )
    self.setDescription( 'Choose the applicator you are using. It will load the right template.' )
    self.__parent = super( NFSelectApplicatorStep, self )
    self.fourPointsCheckbox = qt.QRadioButton('')
    self.threePointsCheckbox = qt.QRadioButton('')
    self.threePointsCornersCheckbox = qt.QRadioButton('')

  def createUserInterface( self ):
  
    self.__layout = self.__parent.createUserInterface()

    self.fourPointsCheckbox = qt.QRadioButton("Syed-Neblett Template and Obturator 4 points")
    self.fourPointsCheckbox.setChecked(1)
    
    self.threePointsCheckbox = qt.QRadioButton("Syed-Neblett Template and Obturator 3 points")

    self.threePointsCornersCheckbox = qt.QRadioButton("Syed-Neblett Template 3 points in corners")

    self.__layout.addRow(self.fourPointsCheckbox)
    self.__layout.addRow(self.threePointsCheckbox)
    self.__layout.addRow(self.threePointsCornersCheckbox)

    #--------------------------------------------
    # to be used in the future

    # threePointsCheckbox = qt.QCheckBox("Intrauterine Tandem")
    # checkBox4 = qt.QCheckBox("Intravaginal Ovoids")
    # checkBox5 = qt.QCheckBox("Seed marker")
    # checkBox6 = qt.QCheckBox("Rings")
    # checkBox7 = qt.QCheckBox("Utrecht")
    # checkBox8 = qt.QCheckBox("Wien")
    
    # self.__layout.addRow(checkBox4)
    # self.__layout.addRow(checkBox5)
    # self.__layout.addRow(checkBox6)
    # self.__layout.addRow(checkBox7)
    # self.__layout.addRow(checkBox8)
    # self.updateWidgetFromParameters(self.parameterNode())
    qt.QTimer.singleShot(0, self.killButton)
      
  def killButton(self):
    # hide useless button
    bl = slicer.util.findChildren(text='NeedleSegmentation')
    if len(bl):
      bl[0].hide()

  def onEntry(self,comingFrom,transitionType):
  
    super(NFSelectApplicatorStep, self).onEntry(comingFrom, transitionType)
    # setup the interface
    pNode = self.parameterNode()
    #print pNode
    pNode.SetParameter('currentStep', self.stepid)
    #print 'NFSelectApplicatorStep'
    # if pNode.GetParameter('skip')=='1':
    #   self.workflow().goForward() # 3       


  def onExit(self, goingTo, transitionType):
    pNode = self.parameterNode()
    if pNode.GetParameter('skip')!='1':
      if self.fourPointsCheckbox.isChecked():
        pNode.SetParameter('Template', "4points")
      if self.threePointsCheckbox.isChecked():
        pNode = self.parameterNode()
        pNode.SetParameter('Template', "3points") 
      if self.threePointsCornersCheckbox.isChecked():
        pNode = self.parameterNode()
        pNode.SetParameter('Template', "3pointsCorners")       
    if goingTo.id() != 'SelectProcedure' and goingTo.id() != 'LoadModel':
      return

    super(NFSelectApplicatorStep, self).onExit(goingTo, transitionType)

  def validate( self, desiredBranchId ):
    '''
    here, nothing to validate
    '''
    self.__parent.validate( desiredBranchId )    
    self.__parent.validationSucceeded(desiredBranchId)