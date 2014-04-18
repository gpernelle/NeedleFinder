# slicer imports
from __main__ import vtk, slicer

# python includes
import sys
import time

class Helper( object ):
  '''
  classdocs
  '''
  @staticmethod
  def SetBgFgVolumes(bg, fg):
    appLogic = slicer.app.applicationLogic()
    selectionNode = appLogic.GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID(bg)
    selectionNode.SetReferenceSecondaryVolumeID(fg)
    appLogic.PropagateVolumeSelection()

  @staticmethod
  def SetLabelVolume(lb):
    appLogic = slicer.app.applicationLogic()
    selectionNode = appLogic.GetSelectionNode()
    selectionNode.SetReferenceActiveLabelVolumeID(lb)
    appLogic.PropagateVolumeSelection()


  @staticmethod
  def GetNthStepId( n ):
    steps = [None, # 0
             'SelectProcedure', # 1
             'SelectApplicator', # 2
             'LoadModel', # 3
             'FirstRegistration', # 4
             'SecondRegistration', # 5
             'NeedlePlanning', # 6
             'NeedleSegmentation'] # 7

    if n < 0 or n > len( steps ): n = 0
    return steps[n]

  @staticmethod
  def GenericMessage( message, type = ""):
    if not type == "": type = " %s:" % type
    str_time = time.strftime( "%m/%d/%Y %H:%M:%S" )
    print "[EMSegmentPy %s]:%s %s" %(str_time, type, str(message))
    sys.stdout.flush()

  @staticmethod
  def Info( message ):
    Helper.GenericMessage(message)

  @staticmethod
  def Warning( message ):
    Helper.GenericMessage(message, "WARNING")

  @staticmethod
  def Error( message ):
    Helper.GenericMessage(message, "ERROR")

  @staticmethod
  def Debug( message ):
    showDebugOutput = 0
    if showDebugOutput:
      Helper.GenericMessage(message, "DEBUG")