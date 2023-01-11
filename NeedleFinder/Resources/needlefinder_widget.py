import time
import numpy as np
import random
import vtk, qt, ctk, slicer

from Resources.needlefinder_logic import NeedleFinderLogic
from Resources.utils import *
from Resources.constants.settings import *


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
        self.observerTagsFid = {}
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
        self.dirDialog = None
        self.logic = NeedleFinderLogic()
        self.needleValidationClicks = 1
        self.addManualTipClicks = 2
        self.addCTLPoints = 14
        self.obturatorNeedleTipClicks = 3
        self.caseNr = 0
        self.userNr = 0
        self.logDir = "/tmp"  # TODO this is not windows compatible

        # table report
        self.table = None
        self.tableCTL = None
        self.view = None
        self.viewCTL = None
        self.model = None
        self.modelCTL = None

        self.initObturatorNeedles()

        # keep list of pairs: [observee,tag] so they can be removed easily
        self.styleObserverTags = []
        # keep a map of interactor styles to sliceWidgets so we can easily get sliceLogic
        self.sliceWidgetsPerStyle = {}
        # self.refreshObservers()

        self.CrosshairNode = None
        self.CrosshairNodeObserverTag = None

        # crosshairnode use to get mouse position
        self.CrosshairNode = slicer.mrmlScene.GetNthNodeByClass(
            0, "vtkMRMLCrosshairNode"
        )
        if self.CrosshairNode:
            self.CrosshairNodeObserverTag = self.CrosshairNode.AddObserver(
                slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent,
                self.processEvent,
            )

        # segmentation editor variables
        self.editorWidget = None
        self.editUtil = None
        self.undoRedo = None
        self.wandLogics = {}
        self.labelMapNode = None
        self.currentLabel = None
        self.tempPointList = []
        self.undoListFid = [{} for i in range(30)]

    def __del__(self):
        self.removeObservers()

    def getName(self):
        """
        return class name
        """
        return self.__class__.__name__

    def initObturatorNeedles(self):
        self.obtuNeedle = 0
        self.obtuNeedleValueCtrPt = [
            [[999, 999, 999] for i in range(10)] for j in range(10)
        ]
        self.obtuNeedlePt = [[[999, 999, 999] for i in range(10)] for j in range(10)]

    # ----------------------------------------------------------------------------------------------
    """ Needle Segmentation report"""
    # ----------------------------------------------------------------------------------------------

    def initTableView(self):
        """
        Initialize a table gathering information on segmented needles
        Model and view for stats table
        """
        # productive
        profprint()
        if self.table is None:
            # self.keys = ("#")
            # self.keys = ("#","Round" ,"Reliability")
            self.keys = "#"
            self.labelStats = {"Labels": []}
            self.items = []
            if self.model is None:
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
                if self.view is None:
                    self.view = qt.QTableView()
                    self.view.setMinimumHeight(300)
                    self.view.sortingEnabled = True
                    self.view.verticalHeader().visible = False
                    self.view.horizontalHeader().setStretchLastSection(True)

                self.view.setModel(self.model)
                self.view.setColumnWidth(0, 18)
                self.view.setColumnWidth(1, 58)
                self.view.setColumnWidth(2, 58)
                self.table = 1
                self.row = 0
                self.col = 0
                slicer.modules.NeedleFinderWidget.analysisGroupBoxLayout.addRow(
                    self.view
                )

    # ----------------------------------------------------------------------------------------------
    """ Manual Control Points report"""
    # ----------------------------------------------------------------------------------------------

    def initTableViewControlPoints(self):
        """
        Initialize a table gathering control points from manual segmentation
        """
        # productive
        profprint()
        if self.tableCTL is None:
            self.keysCTL = "#"
            self.labelStatsCTL = {}
            self.labelStatsCTL["Labels"] = []
            self.labelStatsCTL["ID"] = []
            self.itemsCTL = []
            if self.modelCTL is None:
                self.modelCTL = qt.QStandardItemModel()
                self.modelCTL.setColumnCount(5)
                self.modelCTL.setHeaderData(0, 1, "")
                self.modelCTL.setHeaderData(1, 1, "# Needle")
                self.modelCTL.setHeaderData(2, 1, "# Point")

                self.modelCTL.setHeaderData(3, 1, "Delete")
                self.modelCTL.setHeaderData(4, 1, "Reformat")
                self.modelCTL.setHeaderData(5, 1, "Comments")
                if self.viewCTL is None:
                    self.viewCTL = qt.QTableView()
                    self.viewCTL.setMinimumHeight(300)
                    self.viewCTL.sortingEnabled = True
                    self.viewCTL.verticalHeader().visible = False
                    self.viewCTL.horizontalHeader().setStretchLastSection(True)

                self.viewCTL.setModel(self.modelCTL)
                self.viewCTL.setColumnWidth(0, 18)
                self.viewCTL.setColumnWidth(1, 58)
                self.viewCTL.setColumnWidth(2, 58)
                self.tableCTL = 1
                self.rowCTL = 0
                self.colCTL = 0
                self.analysisGroupBoxLayoutCTL.addRow(self.viewCTL)

    def createAddOrSelectLabelMapNode(self, script=False):
        """
        Create label map node for Segmentation editor and needle finder.
        """
        # productive
        profprint()
        print("creating label map for working intensity volume")
        # create, select label map
        volLogic = slicer.modules.volumes.logic()
        sliceLogic = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
        vn = sliceLogic.GetBackgroundLayer().GetVolumeNode()
        try:
            self.labelMapNode = slicer.util.getNode(vn.GetName())
        except:
            self.labelMapNode = volLogic.CreateAndAddLabelVolume(
                slicer.mrmlScene, vn, vn.GetName() + "-label"
            )
        # select label volume
        if (
            not script
        ):  # TODO guess there is a bug here (at least while testing with parSearch): also changes the main volume!!
            selectionNode = slicer.app.applicationLogic().GetSelectionNode()
            selectionNode.SetReferenceActiveLabelVolumeID(self.labelMapNode.GetID())
            # slicer.app.applicationLogic().PropagateVolumeSelection() #<<<this line causes unpredictable volume switching
            # set half transparency
            scRed = slicer.app.layoutManager().sliceWidget("Red").sliceController()
            scRed.setLabelMapOpacity(0.5)
            scYel = slicer.app.layoutManager().sliceWidget("Yellow").sliceController()
            scYel.setLabelMapOpacity(0.5)
            scGrn = slicer.app.layoutManager().sliceWidget("Green").sliceController()
            scGrn.setLabelMapOpacity(0.5)
            # enable label map outline display mode
            sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
            if sRed is None:
                sRed = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode1")
            sRed.SetUseLabelOutline(1)
            sYel = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeYellow")
            if sYel is None:
                sYel = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
            sYel.SetUseLabelOutline(1)
            sGrn = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
            if sGrn is None:
                sGrn = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode3")
            sGrn.SetUseLabelOutline(1)
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
        # -----------------------------------------------------------------------------
        # Needle Finder Logic
        logic = self.logic

        # Report Frame########################################
        self.__reportFrame = ctk.ctkCollapsibleButton()
        self.__reportFrame.text = "Segmentation Report"
        self.__reportFrame.collapsed = 1
        reportFrame = qt.QFormLayout(self.__reportFrame)

        # segmentation report
        self.analysisGroupBox = qt.QGroupBox()
        self.analysisGroupBox.setFixedHeight(330)
        self.analysisGroupBox.setTitle("Segmentation Report")
        reportFrame.addRow(self.analysisGroupBox)
        self.analysisGroupBoxLayout = qt.QFormLayout(self.analysisGroupBox)

        # -----------------------------------------------------------------------------

        # Report Frame Control Point########################################
        self.__reportFrameCTL = ctk.ctkCollapsibleButton()
        self.__reportFrameCTL.text = "Manual Segmentation Report"
        self.__reportFrameCTL.collapsed = 1
        reportFrameCTL = qt.QFormLayout(self.__reportFrameCTL)

        # manual segmentation report
        self.analysisGroupBoxCTL = qt.QGroupBox()
        self.analysisGroupBoxCTL.setFixedHeight(330)
        self.analysisGroupBoxCTL.setTitle("Manual Segmentation Report")
        reportFrameCTL.addRow(self.analysisGroupBoxCTL)
        self.analysisGroupBoxLayoutCTL = qt.QFormLayout(self.analysisGroupBoxCTL)

        # -----------------------------------------------------------------------------

        # Segmentation Frame##########################################
        self.__segmentationFrame = ctk.ctkCollapsibleButton()
        self.__segmentationFrame.text = "Segmentation"
        self.__segmentationFrame.collapsed = 0
        segmentationFrame = qt.QFormLayout(self.__segmentationFrame)

        # 1 Define template
        self.templateSliceButton = qt.QPushButton(
            "1. Select Current Axial Slice as Seg. Limit (current: None)"
        )
        segmentationFrame.addRow(self.templateSliceButton)
        self.templateSliceButton.connect("clicked()", logic.placeAxialLimitMarker)
        self.templateSliceButton.setEnabled(1)

        # 2 give needle tips
        self.fiducialButton = qt.QPushButton(
            "2. Start Giving Needle Tips [CTRL + ENTER]"
        )
        self.fiducialButton.checkable = True
        segmentationFrame.addRow(self.fiducialButton)
        self.fiducialButton.connect(
            "toggled(bool)", self.onStartStopGivingNeedleTipsToggled
        )
        self.fiducialButton.setEnabled(0)

        # New insertion - create new set of needles with different colors
        self.newInsertionButton = None
        # self.newInsertionButton = qt.QPushButton('New Needle Set')
        # segmentationFrame.addRow(self.newInsertionButton)
        # self.newInsertionButton.connect('clicked()', logic.newInsertionNeedleSet)
        # self.newInsertionButton.setEnabled(0)

        # Delete Needle Button
        self.deleteNeedleButton = qt.QPushButton(
            "Delete Last Segmented Needle [Ctrl + Z]"
        )
        segmentationFrame.addRow(self.deleteNeedleButton)
        # self.deleteNeedleButton.connect('clicked()', logic.deleteAllAutoNeedlesFromScene)
        self.deleteNeedleButton.connect("clicked()", logic.deleteLastNeedle)
        self.deleteNeedleButton.setEnabled(0)

        # Reset Needle Detection Button
        self.resetDetectionButton = qt.QPushButton(
            "Reset Needle Detection (Start Over)"
        )
        segmentationFrame.addRow(self.resetDetectionButton)
        self.resetDetectionButton.connect("clicked()", logic.resetNeedleDetection)
        self.resetDetectionButton.setEnabled(0)

        # auto segmentation report
        segmentationFrame.addRow(self.__reportFrame)

        # Validation Frame##########################################
        self.__validationFrame = ctk.ctkCollapsibleButton()
        self.__validationFrame.text = "Validation"
        self.__validationFrame.collapsed = 0  # <<<
        validationFrame = qt.QFormLayout(self.__validationFrame)

        self.startGivingControlPointsButton = qt.QPushButton(
            "Start Giving Control Points"
        )
        self.startGivingControlPointsButton.checkable = True
        self.startGivingControlPointsButton.setStyleSheet(
            "QPushButton {background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #ccffcc, stop: 1 #f3fff3)}"
            "QPushButton:checked{background-color: red;}"
        )

        self.startGivingControlPointsButton.connect(
            "toggled(bool)", self.onStartStopGivingValidationControlPointsToggled
        )

        self.startAssistModeButton = qt.QPushButton("Assisted Manual Segmentation")
        self.startAssistModeButton.checkable = True
        self.startAssistModeButton.connect(
            "toggled(bool)", self.onStartAssistModeToggled
        )

        self.validationNeedleButton = qt.QPushButton("Next Validation Needle: (0)->(1)")
        self.validationNeedleButton.toolTip = (
            "By clicking on this button, you will increment the number of the needle"
        )
        self.validationNeedleButton.toolTip += "that you want to manually segment. Thus, the points you will add will be used to draw a new needle.<br/>"
        self.validationNeedleButton.toolTip += "<b>Warning:<b> You can/'t add any more points to the current needle after clicking here"

        self.validationNeedleButton.connect("clicked()", logic.validationNeedle)

        self.drawValidationNeedlesButton = qt.QPushButton("Render Manual Needle 0")
        self.drawValidationNeedlesButton.toolTip = "Redraw every manually segmented needles. This is usefull for example if you moved a control point, or after you added a new needle"

        self.drawValidationNeedlesButton.connect(
            "clicked()", logic.drawValidationNeedles
        )

        self.startValidationButton = qt.QPushButton("Start Evaluation")
        self.startValidationButton.toolTip = (
            "Launch tracking algo. from the tip of the manually segmented needles"
        )

        self.startValidationButton.connect("clicked()", logic.startValidation)
        # self.startValidationButton.setStyleSheet("background-color: yellow")
        self.startValidationButton.setStyleSheet(
            "background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f7f700, stop: 1 #dbdb00)"
        )

        # Reset Needle Validation Button
        self.resetValidationButton = qt.QPushButton("Reset Manual Segmentation")
        self.templateRegistrationButton = qt.QPushButton("[Beta] Template Registration")

        # Hide Markers Button
        self.hideAnnotationTextButton = qt.QPushButton("Hide Marker Texts")
        self.hideAnnotationTextButton.checkable = True

        # Undo Button
        self.undoButton = qt.QPushButton("Undo Fiducial Mvt")
        self.undoButton.checkable = False

        self.resetValidationButton.connect("clicked()", logic.resetNeedleValidation)
        self.templateRegistrationButton.connect("clicked()", logic.autoregistration)
        self.hideAnnotationTextButton.connect("clicked()", logic.hideAnnotations)
        self.undoButton.connect("clicked()", logic.undoFid)

        self.editNeedleTxtBox = qt.QSpinBox()
        self.editNeedleTxtBox.connect("valueChanged(int)", logic.changeValue)
        editLabel = qt.QLabel("Choose Needle:")

        # Choose needle
        self.configFrameCTL = qt.QFrame()
        self.configFrameCTL.setLayout(qt.QHBoxLayout())

        self.configFrameCTL.layout().addWidget(editLabel)
        self.configFrameCTL.layout().addWidget(self.editNeedleTxtBox)
        self.configFrameCTL.layout().addWidget(self.validationNeedleButton)

        # validationFrame.addRow(editLabel, self.editNeedleTxtBox)
        # validationFrame.addRow(self.validationNeedleButton)
        validationFrame.layout().addRow(self.configFrameCTL)
        validationFrame.addRow(self.startGivingControlPointsButton)
        validationFrame.addRow(self.startAssistModeButton)
        validationFrame.addRow(self.drawValidationNeedlesButton)
        validationFrame.addRow(self.startValidationButton)
        validationFrame.addRow(self.resetValidationButton)
        validationFrame.addRow(self.hideAnnotationTextButton)
        validationFrame.addRow(self.undoButton)
        # validationFrame.addRow(self.templateRegistrationButton)
        validationFrame.addRow(self.__reportFrameCTL)

        # self.scrollPointButton = qt.QPushButton('Scroll Ctrl Pt for Needle ' + str(self.editNeedleTxtBox.value))
        # validationFrame.addRow(self.scrollPointButton)
        # self.scrollPointButton.connect('clicked()', logic.scrollPoint)

        # Needle detection parameters#################################
        self.__parameterFrame = ctk.ctkCollapsibleButton()
        self.__parameterFrame.text = "Needle Detection Parameters (Developers)"
        self.__parameterFrame.collapsed = 0
        parameterFrame = qt.QFormLayout(self.__parameterFrame)

        # Load/Save/Reset
        self.configFrame = qt.QFrame()
        self.configFrame.setLayout(qt.QHBoxLayout())
        parameterFrame.layout().addRow(self.configFrame)
        self.loadButton = qt.QPushButton()
        self.loadButton.text = "Load Parameters"
        self.loadButton.checkable = False
        self.loadButton.toolTip = "Click to load parameters from a configuration file."
        self.loadButton.connect("clicked()", self.onLoad)
        self.saveButton = qt.QPushButton()
        self.saveButton.checkable = False
        self.saveButton.text = "Save Parameters"
        self.saveButton.toolTip = (
            "Click to save the parameters in a configuration file."
        )
        self.saveButton.connect("clicked()", self.onSave)
        self.resetParametersButton = qt.QPushButton()
        self.resetParametersButton.checkable = False
        self.resetParametersButton.text = "Reset Default Parameters"
        self.resetParametersButton.toolTip = (
            "Click to reset the default parameters from default.cfg"
        )
        self.resetParametersButton.connect("clicked()", self.onResetParameters)
        self.configFrame.layout().addWidget(self.loadButton)
        self.configFrame.layout().addWidget(self.saveButton)
        self.configFrame.layout().addWidget(self.resetParametersButton)

        # Auto correct tip position?
        self.autoCorrectTip = qt.QCheckBox("Auto correct tip position?")
        parameterFrame.addRow(self.autoCorrectTip)
        self.autoCorrectTip.setChecked(0)

        # Look for needles in CT?
        self.invertedContrast = qt.QCheckBox("Search for bright needles (CT)?")
        parameterFrame.addRow(self.invertedContrast)
        # Compute gradient?
        self.gradient = qt.QCheckBox("Compute gradient?")
        self.gradient.setChecked(1)
        parameterFrame.addRow(self.gradient)

        # Filter ControlPoints?
        self.filterControlPoints = qt.QCheckBox("Filter Control Points?")
        self.filterControlPoints.setChecked(0)
        # parameterFrame.addRow(self.filterControlPoints)

        # Draw Fiducial Points?
        self.drawFiducialPoints = qt.QCheckBox("Draw Control Points?")
        self.drawFiducialPoints.setChecked(0)
        parameterFrame.addRow(self.drawFiducialPoints)

        # Auto find Tips: Tracking in +z and -z direction
        self.autoStopTip = qt.QCheckBox("Tracking in both directions")
        self.autoStopTip.setChecked(0)
        parameterFrame.addRow(self.autoStopTip)

        # Extend Needle to the wanted value
        self.extendNeedle = qt.QCheckBox("Extend Needle")
        self.extendNeedle.setChecked(0)
        parameterFrame.addRow(self.extendNeedle)

        # Real Needle Value (used to extend the needle)
        realNeedleLengthLabel = qt.QLabel("Real Needle Length (mm):")
        self.realNeedleLength = qt.QSpinBox()
        self.realNeedleLength.setMinimum(0.1)
        self.realNeedleLength.setMaximum(1500)
        self.realNeedleLength.setValue(240)
        parameterFrame.addRow(realNeedleLengthLabel, self.realNeedleLength)

        # Max Needle Length?
        self.maxLength = qt.QCheckBox("Max Needle Length?")
        self.maxLength.setChecked(1)
        parameterFrame.addRow(self.maxLength)

        # Add Gaussian Estimation?
        self.gaussianAttenuationButton = qt.QCheckBox("Add Gaussian Prob. Attenuation?")
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
        parameterFrame.addRow(
            numberOfPointsPerNeedleLabel, self.numberOfPointsPerNeedle
        )

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
        self.algoVersParameter.setMaximum(9)
        self.algoVersParameter.setValue(0)
        algoLabel = qt.QLabel("Needle detection version: ")
        parameterFrame.addRow(algoLabel, self.algoVersParameter)

        # Research/dev. area#################################
        self.__devFrame = ctk.ctkCollapsibleButton()
        self.__devFrame.text = "R&&D (Developers)"
        self.__devFrame.collapsed = 0
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

        self.skipSegLimitButton = qt.QPushButton("Skip Giving Seg. Limit.")
        self.skipSegLimitButton.checkable = False
        self.skipSegLimitButton.connect("clicked(bool)", self.onSkipSegLimit)

        # Obturator needle tips
        self.fiducialObturatorButton = qt.QPushButton(
            "Start Giving Obturator Needle Tips"
        )
        self.fiducialObturatorButton.checkable = True
        self.fiducialObturatorButton.connect(
            "toggled(bool)", self.onStartStopGivingObturatorNeedleTipsToggled
        )

        self.renderObturatorNeedlesButton = qt.QPushButton("Render Obturator Needles")
        self.renderObturatorNeedlesButton.checkable = False
        self.renderObturatorNeedlesButton.connect(
            "clicked()", self.logic.drawObturatorNeedles
        )

        self.displayFiducialButton = qt.QPushButton("Display Labels On Needles")
        self.displayFiducialButton.connect("clicked()", logic.displayFiducial)

        self.displayContourButton = qt.QPushButton("Draw Radiation Isosurfaces")
        self.displayContourButton.checkable = False
        self.displayContourButton.connect("clicked()", logic.drawIsoSurfaces)

        self.hideContourButton = qt.QPushButton("Hide Radiation Isosurfaces")
        self.hideContourButton.checkable = True
        self.hideContourButton.connect("clicked()", logic.hideIsoSurfaces)
        self.hideContourButton.setEnabled(0)

        self.filterButton = qt.QPushButton("Preprocessing")
        self.filterButton.checkable = False
        self.filterButton.connect("clicked()", logic.filterWithSITK)
        self.filterButton.setEnabled(1)

        self.parSearchButton = qt.QPushButton("Parameter Search")
        self.parSearchButton.checkable = False
        self.parSearchButton.connect("clicked()", logic.parSearch)
        self.parSearchButton.setEnabled(1)

        self.setAsValNeedlesButton = qt.QPushButton("Use Needles for Validation")
        self.setAsValNeedlesButton.checkable = False
        self.setAsValNeedlesButton.connect(
            "clicked()", logic.setAllNeedleTubesAsValidationNeedles
        )
        self.setAsValNeedlesButton.setEnabled(1)
        self.setAsValNeedlesButton.setStyleSheet(
            "background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f7f700, stop: 1 #dbdb00)"
        )

        # ## create segmentation editor environment:
        editorWidgetParent = slicer.qMRMLWidget()
        editorWidgetParent.setLayout(qt.QVBoxLayout())
        editorWidgetParent.setMRMLScene(slicer.mrmlScene)
        editorWidgetParent.hide()
        # The order of statements is important here for resetNeedleDetection to work!!
        # self.editorWidget = EditorWidget(editorWidgetParent, False)
        self.editorWidget = slicer.modules.segmenteditor.createNewWidgetRepresentation()
        # self.editUtil = self.editorWidget.editUtil  # EditorLib.EditUtil.EditUtil()
        self.currentLabel = None
        self.setWandEffectOptions()  # has to be done before setup():
        # self.editUtil.setCurrentEffect("DefaultTool")
        self.editorWidget.setup()
        # our mouse mode button
        self.editorWidget.toolsBox.actions["NeedleFinder"] = qt.QAction(
            0
        )  # dummy self.fiducialButton
        # self.undoRedo = self.editorWidget.toolsBox.undoRedo
        self.currentLabel = self.editUtil.getLabel()
        self.editorWidget.editLabelMapsFrame.setText("Edit Segmentation")
        self.editorWidget.editLabelMapsFrame.connect(
            "contentsCollapsed(bool)", self.onEditorCollapsed
        )
        editorWidgetParent.show()
        self.editUtil.setCurrentEffect("NeedleFinder")

        self.scenePath = qt.QLineEdit()
        self.cleanSceneButton = qt.QPushButton("Clean Scene")
        self.cleanSceneButton.connect("clicked()", logic.cleanScene)

        # devFrame.addRow(self.displayFiducialButton)
        devFrame.addWidget(editorWidgetParent)
        devFrame.addRow(self.scenePath)
        devFrame.addRow(self.cleanSceneButton)
        devFrame.addRow(self.skipSegLimitButton)
        devFrame.addRow(self.fiducialObturatorButton)
        devFrame.addRow(self.renderObturatorNeedlesButton)
        devFrame.addRow(self.displayContourButton)
        devFrame.addRow(self.hideContourButton)
        devFrame.addRow(self.filterButton)
        devFrame.addRow(self.parSearchButton)
        devFrame.addRow(self.setAsValNeedlesButton)
        devFrame.addRow(self.templateRegistrationButton)

        # put frames on the tab########################################
        self.layout.addRow(self.__segmentationFrame)
        # self.layout.addRow(self.__reportFrame)
        # self.layout.addRow(self.__reportFrameCTL)
        self.layout.addRow(self.__validationFrame)
        self.layout.addRow(self.__parameterFrame)
        self.layout.addRow(self.__devFrame)

        # reset module
        resetButton = qt.QPushButton("Reset Module")
        resetButton.connect("clicked()", self.onReload)
        self.widget = slicer.qMRMLWidget()
        self.widget.setLayout(self.layout)
        self.layout2.addWidget(self.widget)

        # init table report
        self.initTableView()  # init the report table
        self.initTableViewControlPoints()  # init the report table

        # Lauren's feature request: set mainly unused coronal view to sagittal to display ground truth bitmap image (if available)
        # # Usage after fresh slicer start: 1. Load scene and 2. reference jpg. 3. Then open NeedleFinder from Modules selector
        # vnJPG = slicer.util.getNode("Case *")  # the naming convention for the ground truth JPG files: "Case XXX.jpg"
        # if vnJPG:
        #   print "showing ground 2d image truth in green view"
        #   # show JPG image if available
        #   sw = slicer.app.layoutManager().sliceWidget("Green")
        #   cn = sw.mrmlSliceCompositeNode()
        #   cn.SetBackgroundVolumeID(vnJPG.GetID())
        #   slicer.app.layoutManager().sliceWidget("Green").sliceLogic().GetBackgroundLayer().Modified()
        #   sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeGreen")
        #   if sGreen is None :
        #     sGreen = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNode2")
        #   # set to axial view
        #   sGreen.SetSliceVisible(0)
        #   sGreen.SetOrientationToAxial()
        #   sw.fitSliceToBackground()
        #   sGreen.Modified()

        self.onResetParameters()
        self.setupShortcuts()

    def setWandEffectOptions(self, tolerance=20, maxPixels=200, fillMode="Volume"):
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
        print("You Pressed: " + event.text())

    def setupShortcuts(self):
        """
        Set up hot keys for various actions.
        """
        # productive
        profprint()
        macros = (
            ("Ctrl+Return", self.segmentNeedle),
            ("Ctrl+z", self.logic.deleteLastNeedle),
            ("Ctrl+y", self.acceptNeedleTipEstimate),
            ("Ctrl+n", self.rejectNeedleTipEstimate),
            ("Ctrl+u", self.acceptNeedleTipEstimateAsNewTempMarker),
        )

        for keys, f in macros:
            k = qt.QKeySequence(keys)
            s = qt.QShortcut(k, slicer.util.mainWindow())
            s.connect("activated()", f)
            s.connect("activatedAmbiguously()", f)
            print(f"'{keys}' -> '{f.__name__}'")
            # convenient for the python console
            globals()["nfw"] = nfw = slicer.modules.NeedleFinderWidget
            globals()["nfl"] = nfl = slicer.modules.NeedleFinderWidget.logic
            print("nfl -> NeedleFinderLogic")
            print("nfw -> NeedleFinderWidget")

    def segmentNeedle(self):
        """
        helper function for Ctrl+Enter
        """
        # productive #event
        profprint()
        if self.fiducialButton.isEnabled():
            print("new checked state: ", not self.fiducialButton.checked)
            self.onStartStopGivingNeedleTipsToggled(not self.fiducialButton.checked)

    def rejectNeedleTipEstimate(self):
        """
        Helper function for Ctrl+n: delete tip est. and jump back to temp marker
        """
        # productive #event
        profprint()
        # delete needle tip estimate fiducial
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                slicer.mrmlScene.RemoveNode(node)
        # jump back to temp marker
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
        rasTemp = [0, 0, 0]
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                node.GetFiducialCoordinates(rasTemp)
        slRed = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
        slYel = slicer.app.layoutManager().sliceWidget("Yellow").sliceLogic()
        slGrn = slicer.app.layoutManager().sliceWidget("Green").sliceLogic()
        slRed.SetSliceOffset(rasTemp[2])
        slYel.SetSliceOffset(rasTemp[0])
        self.logic.resetCoronalSegment()
        slGrn.SetSliceOffset(rasTemp[1])
        node = slicer.util.getNode("*.tempN")
        slicer.mrmlScene.RemoveNode(node)

    def acceptNeedleTipEstimate(self):
        """
        Helper function for Ctrl+y: delete temp and est. tip markers and start needle detection from est. tip.
        """
        # productive #event
        profprint()
        volumeNode = (
            slicer.app.layoutManager()
            .sliceWidget("Red")
            .sliceLogic()
            .GetBackgroundLayer()
            .GetVolumeNode()
        )
        imageData = volumeNode.GetImageData()
        spacing = volumeNode.GetSpacing()
        colorVar = random.randrange(50, 100, 1)  # ???/(100.)
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
        coord = [0, 0, 0]
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                node.GetFiducialCoordinates(coord)
        if sum(coord):
            self.logic.needleDetectionThread(
                self.logic.ras2ijk(coord), imageData, colorVar, spacing
            )
        if self.autoStopTip.isChecked():
            self.logic.needleDetectionUPThread(ijk, imageData, colorVar, spacing)
        # change requested by Lauren: remove temp marker after detection
        print("deleting temp marker and segmentation")
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                slicer.mrmlScene.RemoveNode(node)
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                slicer.mrmlScene.RemoveNode(node)
        self.tempPointList = []
        self.logic.resetCoronalSegment()
        node = slicer.util.getNode("*.tempN")
        slicer.mrmlScene.RemoveNode(node)

    def acceptNeedleTipEstimateAsNewTempMarker(self):
        """
        Helper function for Ctrl+u: delete temp and est. tip markers and start needle up detection again from est. tip.
        """
        # productive #event
        profprint()
        volumeNode = (
            slicer.app.layoutManager()
            .sliceWidget("Red")
            .sliceLogic()
            .GetBackgroundLayer()
            .GetVolumeNode()
        )
        imageData = volumeNode.GetImageData()
        spcg = volumeNode.GetSpacing()
        org = volumeNode.GetOrigin()
        colorVar = random.randrange(50, 100, 1)  # ???/(100.)
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
        coord = [0, 0, 0]
        for i in range(tempFidNodes.GetNumberOfItems()):
            node = tempFidNodes.GetItemAsObject(i)
            if node:
                node.GetFiducialCoordinates(coord)
                ijk = self.logic.ras2ijk(coord)
                rasPrevTip = self.logic.ijk2ras(ijk)
        # delete old temp tube
        node = slicer.util.getNode("*.tempN")
        slicer.mrmlScene.RemoveNode(node)
        if sum(coord):
            self.logic.controlPoints = []  # delete old control points from previous try
            ijkTipEstimate = self.logic.needleDetectionUPThread(
                ijk,
                imageData,
                colorVar,
                spcg,
                tipOnly=False,
                strName=".tempN",
                script=True,
            )
            rasTipEstimate = self.logic.ijk2ras(ijkTipEstimate)
        print("moving temp markers to new segment")
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
        # if fiducial exists, move it to new location
        ras = self.logic.ijk2ras(ijkTipEstimate)
        if tempFidNodes.GetNumberOfItems() > 0:
            for i in range(tempFidNodes.GetNumberOfItems()):
                node = tempFidNodes.GetItemAsObject(i)
                if node:
                    node.SetFiducialCoordinates(ras)
        # if fiducial exists, move it to new location
        tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
        if tempFidNodes.GetNumberOfItems() > 0:
            for i in range(tempFidNodes.GetNumberOfItems()):
                node = tempFidNodes.GetItemAsObject(i)
                if node:
                    node.SetFiducialCoordinates(rasPrevTip)
                    self.tempPointList.append(rasPrevTip)  # [0],ras[1],ras[2])
                    print("tempPointList: ", self.tempPointList)
        # update segments
        slRed = slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
        slYel = slicer.app.layoutManager().sliceWidget("Yellow").sliceLogic()
        # slGrn=slicer.app.layoutManager().sliceWidget("Green").sliceLogic()
        node = slicer.util.getNode("*.tempN")
        if node:
            self.logic.reformatCoronalView4NeedleSegment(
                rasPrevTip, rasTipEstimate
            )  # (base=[],tip=[],ID=node.GetID().lstrip('vtkMRMLModelNode'))
        kx = 1 + ijkTipEstimate[2]
        print("z slice off.: ", (kx - 1) * spcg[2] + org[2])
        slRed.SetSliceOffset((kx - 1) * spcg[2] + org[2])
        print("x slice off.: ", org[0] - ijkTipEstimate[0] * spcg[0])
        slYel.SetSliceOffset(org[0] - ijkTipEstimate[0] * spcg[0])

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
        """When the layout changes, drop the observers from
        all the old widgets and create new observers for the
        newly created widgets"""
        profprint()
        self.removeObservers()
        # get new slice nodes
        layoutManager = slicer.app.layoutManager()
        sliceNodeCount = slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLSliceNode")
        for nodeIndex in range(sliceNodeCount):
            # find the widget for each node in scene
            sliceNode = slicer.mrmlScene.GetNthNodeByClass(
                nodeIndex, "vtkMRMLSliceNode"
            )
            sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())
            if sliceWidget:
                # add obserservers and keep track of tags
                style = sliceWidget.sliceView().interactorStyle()
                self.sliceWidgetsPerStyle[style] = sliceWidget
                # events = ("MouseMoveEvent", "EnterEvent", "LeaveEvent")
                events = (
                    "LeftButtonPressEvent",
                    "RightButtonPressEvent" "KeyPressEvent",
                    "KeyReleaseEvent",
                )
                for event in events:
                    tag = style.AddObserver(event, self.processEvent)
                    self.styleObserverTags.append([style, tag])
            # TODO: also observe the slice nodes

    def onReload(self, moduleName="NeedleFinder"):
        """
        Generic reload method for any scripted module.
        ModuleWizard will subsitute correct default moduleName.
        """
        if profiling:
            profbox()
        # framework
        globals()[moduleName] = slicer.util.reloadScriptedModule(moduleName)

    def onReloadAndTest(self, moduleName="NeedleFinder"):
        """
        Generic reload method for any scripted module.
        ModuleWizard will subsitute correct default moduleName.
        """
        print("onReloadAndTest")
        msgbox(whoami())
        try:
            self.onReload()
            evalString = f'globals()["{moduleName}"].{moduleName}Test()'
            tester = eval(evalString)
            tester.runTest()
        except Exception as e:
            import traceback

            traceback.print_exc()
            qt.QMessageBox.warning(
                slicer.util.mainWindow(),
                "Reload and Test",
                "Exception!\n\n" + str(e) + "\n\nSee Python Console for Stack Trace",
            )

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
            tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
            for i in range(tempFidNodes.GetNumberOfItems()):
                node = tempFidNodes.GetItemAsObject(i)
                if node:
                    slicer.mrmlScene.RemoveNode(node)
        widget.deleteNeedleButton.setEnabled(1)

    def onSkipSegLimit(self):
        """
        Skip providing seg. limit plane, as already in scene.
        """
        profprint()
        # research
        logic = self.logic
        logic.placeAxialLimitMarker(assign=False)

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

    def onStartAssistModeToggled(self, checked):
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
            self.start(self.addCTLPoints)
            self.startAssistModeButton.text = "Stop Assisted Manual Segmentation"
        else:
            self.stop()
            self.startAssistModeButton.text = "Start Assisted Manual Segmentation"

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
        sliceNodeCount = slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLSliceNode")
        for nodeIndex in range(sliceNodeCount):
            # find the widget for each node in scene
            sliceNode = slicer.mrmlScene.GetNthNodeByClass(
                nodeIndex, "vtkMRMLSliceNode"
            )
            sliceWidget = layoutManager.sliceWidget(sliceNode.GetLayoutName())
            if sliceWidget:
                # add obserservers and keep track of tags
                style = sliceWidget.sliceView().interactorStyle()
                self.sliceWidgetsPerStyle[style] = sliceWidget
                events = (
                    "LeftButtonPressEvent",
                    "RightButtonPressEvent",
                    "EnterEvent",
                    "LeaveEvent",
                    "KeyPressEvent",
                    "KeyReleaseEvent",
                )
                for event in events:
                    if process == self.needleValidationClicks:
                        tag = style.AddObserver(
                            event, self.processEventNeedleValidation
                        )
                    elif process == self.addManualTipClicks:
                        tag = style.AddObserver(event, self.processEventAddManualTips)
                    elif process == self.addCTLPoints:
                        tag = style.AddObserver(event, self.processEventAddCTLPoints)
                    elif process == self.obturatorNeedleTipClicks:
                        tag = style.AddObserver(
                            event, self.processEventAddObturatorNeedleTips
                        )
                        dn = (
                            slicer.app.layoutManager()
                            .sliceWidget("Red")
                            .sliceLogic()
                            .GetBackgroundLayer()
                            .GetVolumeNode()
                            .GetDisplayNode()
                        )
                        w = dn.GetWindow()
                        l = dn.GetLevel()
                        dn.AddObserver(
                            vtk.vtkCommand.ModifiedEvent,
                            lambda c, e: logic.setWL(dn, w, l),
                        )
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
        - if shift is pressed, all the temporary fiducial node named '.temp' are removed from the MRML scence
        """
        # productive #frequent #event-handler
        if frequent:
            profprint()
        widget = slicer.modules.NeedleFinderWidget
        logic = slicer.modules.NeedleFinderWidget.logic
        # GET mouse position
        insideView = False
        ras = [0.0, 0.0, 0.0]
        sliceNode = None
        if self.CrosshairNode:
            insideView = self.CrosshairNode.GetCursorPositionRAS(ras)

        if observee in self.sliceWidgetsPerStyle:
            sliceWidget = self.sliceWidgetsPerStyle[observee]
            sliceLogic = sliceWidget.sliceLogic()
            sliceNode = sliceWidget.mrmlSliceNode()
            interactor = observee.GetInteractor()
            key = interactor.GetKeySym()
            # print "Event : ", event
            if 0:
                if event == "KeyPressEvent":  # shift pressed
                    print("key pressed: ", key)
                    if key == "Shift_L" or key == "Shift_R":
                        tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
                        for i in range(tempFidNodes.GetNumberOfItems()):
                            node = tempFidNodes.GetItemAsObject(i)
                            if node:
                                slicer.mrmlScene.RemoveNode(node)

                elif event == "KeyReleaseEvent":  # shift release
                    print("key released: ", key)
                    if key == "Shift_L" or key == "Shift_R":
                        fiducial = slicer.mrmlScene.CreateNodeByClass(
                            "vtkMRMLAnnotationFiducialNode"
                        )
                        fiducial.SetName(".temp")
                        fiducial.Initialize(slicer.mrmlScene)
                        fiducial.SetFiducialCoordinates(ras)
                        fiducial.SetAttribute("TemporaryFiducial", "1")
                        fiducial.SetLocked(True)
                        displayNode = fiducial.GetDisplayNode()
                        displayNode.SetGlyphScale(2)
                        displayNode.SetColor(1, 1, 0)
                        textNode = fiducial.GetAnnotationTextDisplayNode()
                        textNode.SetTextScale(4)
                        textNode.SetColor(1, 1, 0)

            if event == "KeyReleaseEvent" and key == "Shift_L" or key == "Shift_R":
                # print event
                tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
                # if fiducial exists, move it to new location
                if tempFidNodes.GetNumberOfItems() > 0:
                    for i in range(tempFidNodes.GetNumberOfItems()):
                        node = tempFidNodes.GetItemAsObject(i)
                        if node:
                            node.SetFiducialCoordinates(ras)
                            self.tempPointList.append(ras)  # [0],ras[1],ras[2])
                            print("tempPointList: ", self.tempPointList)
                        if sliceLogic not in self.wandLogics:
                            if not self.labelMapNode:
                                self.createAddOrSelectLabelMapNode()
                            print("creating new segment logic")
                            # sliceLogic.SetLabelLayer(...)
                            # wl = EditorLib.WandEffectLogic(sliceLogic)
                            # wl.undoRedo = self.undoRedo
                            # wl.editUtil = self.editUtil
                            # self.wandLogics[sliceLogic] = wl
                        print("tracking needle upwards")
                        self.setWandEffectOptions()  # !! the parameter node can be altered/deleted from outside so re-create/reset option node
                        wl = self.wandLogics[sliceLogic]
                        xy = interactor.GetEventPosition()
                        print("xy: ", xy)
                        if wl.labelAtXY(xy):
                            self.editUtil.setLabel(wl.labelAtXY(xy))
                        else:
                            print("new label")
                            self.currentLabel += 1
                            self.editUtil.setLabel(self.currentLabel)
                        slRed = (
                            slicer.app.layoutManager().sliceWidget("Red").sliceLogic()
                        )
                        slYel = (
                            slicer.app.layoutManager()
                            .sliceWidget("Yellow")
                            .sliceLogic()
                        )
                        slGrn = (
                            slicer.app.layoutManager().sliceWidget("Green").sliceLogic()
                        )
                        volumeNode = slRed.GetBackgroundLayer().GetVolumeNode()
                        imageData = volumeNode.GetImageData()
                        labelImage = self.labelMapNode.GetImageData()
                        ijk = self.logic.ras2ijk(ras)
                        ixStart = ijk[0]
                        jxStart = ijk[1]
                        kxStart = ijk[2]
                        shape = list(labelImage.GetDimensions())
                        spcg = self.labelMapNode.GetSpacing()
                        org = self.labelMapNode.GetOrigin()
                        if widget.algoVersParameter.value > 4:
                            print("wanding")
                            self.wandLogics[sliceLogic].apply(xy)
                            # >>> exp05 walk up (proximal) the found chip from wanding
                            print("shape: ", shape)
                            shape.reverse()
                            ijkMid = None
                            labelArray = vtk.util.numpy_support.vtk_to_numpy(
                                labelImage.GetPointData().GetScalars()
                            ).reshape(shape)
                            # labelArray[labelArray!=self.currentLabel] = 0 #slow, clear old chips
                            # TODO: replace this part by better tip estimation algo
                            for kx in range(
                                max(int(kxStart) - 0, 0),
                                min(int(kxStart + 20 / spcg[2]), shape[0]),
                            ):  # CONST 20mm
                                print("kx", kx)
                                # scan xy slice
                                ijkTipEstimate = ijkMid
                                ijkMid = np.array(
                                    [0, 0, 0]
                                )  # center of mass of pixels in a slice
                                midPtCtr = 0
                                for ix in range(
                                    max(int(ixStart - 10 / spcg[0]), 0),
                                    min(int(ixStart + 10 / spcg[0]), shape[2]),
                                ):  # CONST 10mm
                                    for jx in range(
                                        max(int(jxStart - 10 / spcg[1]), 0),
                                        min(int(jxStart + 10 / spcg[1]), shape[1]),
                                    ):  # CONST 10mm
                                        # try: labelArray[kx,jx,ix]
                                        # except: print "range error ix,jx:", ix, jx
                                        if labelArray[kx, jx, ix] == self.currentLabel:
                                            print(
                                                "curLab, labelArr[x]= ",
                                                self.currentLabel,
                                                labelArray[kx, jx, ix],
                                            )
                                            ijkMid += [ix, jx, kx]
                                            midPtCtr += 1
                                        if (
                                            labelArray[kx, jx, ix]
                                            and labelArray[kx, jx, ix]
                                            != self.currentLabel
                                        ):
                                            labelArray[
                                                kx, jx, ix
                                            ] = 0  # delete old chip?
                                if not midPtCtr:
                                    print(
                                        "empty slice found ijkTipEstimate=",
                                        ijkTipEstimate,
                                    )
                                    break
                                else:
                                    print("non-empty slice found")
                                    # pause()
                                    ijkMid /= float(midPtCtr)
                        else:
                            # TODO: place better alg. here:
                            colorVar = random.randrange(50, 100, 1)  # ???/(100.)
                            ijk = self.logic.ras2ijk(ras)
                            # logic.needleDetectionThread(ijk, imageData, colorVar, spcg)
                            # remove old temp node segment to tip
                            node = slicer.util.getNode("*.tempN")
                            slicer.mrmlScene.RemoveNode(node)
                            print("needle detection upwards")
                            self.logic.controlPoints = (
                                []
                            )  # delete old control points from previous try
                            ijkTipEstimate = logic.needleDetectionUPThread(
                                ijk,
                                imageData,
                                colorVar,
                                spcg,
                                tipOnly=False,
                                strName=".tempN",
                                script=True,
                            )
                            rasTipEstimate = logic.ijk2ras(ijkTipEstimate)
                            kx = 1 + ijkTipEstimate[2]
                            node = slicer.util.getNode("*.tempN")
                            if node:
                                logic.reformatCoronalView4NeedleSegment(
                                    ras, rasTipEstimate
                                )  # node.GetID().lstrip('vtkMRMLModelNode'))
                        # org=[0,0,0]
                        # update slice positions
                        print("z slice off.: ", (kx - 1) * spcg[2] + org[2])
                        slRed.SetSliceOffset((kx - 1) * spcg[2] + org[2])
                        print("x slice off.: ", org[0] - ijkTipEstimate[0] * spcg[0])
                        slYel.SetSliceOffset(org[0] - ijkTipEstimate[0] * spcg[0])
                        # print "y slice off.: ",org[1]-ijkTipEstimate[1]*spcg[1]#+
                        # slGrn.SetSliceOffset(org[1]-ijkTipEstimate[1]*spcg[1])#+org[1])
                        # slRed.SnapSliceOffsetToIJK()
                        # slYel.SnapSliceOffsetToIJK()
                        # slGrn.SnapSliceOffsetToIJK()
                        # look for old tip marker
                        tempFidNodes = slicer.mrmlScene.GetNodesByName(
                            ".tip? [Ctrl+y/n/u]"
                        )
                        for i in range(tempFidNodes.GetNumberOfItems()):
                            node = tempFidNodes.GetItemAsObject(i)
                            if node:
                                node.SetFiducialCoordinates(
                                    logic.ijk2ras(ijkTipEstimate)
                                )
                        if (
                            not tempFidNodes.GetNumberOfItems()
                        ):  # create new ".tip? [Ctrl+y/n]" node
                            fiducial = slicer.mrmlScene.CreateNodeByClass(
                                "vtkMRMLAnnotationFiducialNode"
                            )
                            fiducial.SetName(".tip? [Ctrl+y/n/u]")
                            fiducial.Initialize(slicer.mrmlScene)
                            fiducial.SetFiducialCoordinates(
                                logic.ijk2ras(ijkTipEstimate)
                            )
                            fiducial.SetAttribute("TemporaryTip", "1")
                            fiducial.SetLocked(
                                False
                            )  # movable or not, Lauren wants movable
                            displayNode = fiducial.GetDisplayNode()
                            displayNode.SetGlyphScale(2)
                            displayNode.SetColor(0, 1, 0)
                            textNode = fiducial.GetAnnotationTextDisplayNode()
                            textNode.SetTextScale(4)
                            textNode.SetColor(0, 1, 0)
                        # <<< 50pxe
                else:  # create temp fiducial
                    fiducial = slicer.mrmlScene.CreateNodeByClass(
                        "vtkMRMLAnnotationFiducialNode"
                    )
                    fiducial.SetName(".temp")
                    fiducial.Initialize(slicer.mrmlScene)
                    fiducial.SetFiducialCoordinates(ras)
                    fiducial.SetAttribute("TemporaryFiducial", "1")
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
                volumeNode = (
                    slicer.app.layoutManager()
                    .sliceWidget("Red")
                    .sliceLogic()
                    .GetBackgroundLayer()
                    .GetVolumeNode()
                )
                imageData = volumeNode.GetImageData()
                spacing = volumeNode.GetSpacing()
                ijk = self.logic.ras2ijk(ras)
                print("spacing: ", spacing)
                self.logic.needleDetectionThread(
                    [ijk], imageData, spacing=np.array(spacing)
                )
                if self.autoStopTip.isChecked():
                    self.logic.needleDetectionUPThread(
                        ijk, imageData, colorVar, spacing
                    )
                # change requested by Lauren: remove temp marker after detection
                print("deleting temp marker and segmentation")
                tempFidNodes = slicer.mrmlScene.GetNodesByName(".temp")
                for i in range(tempFidNodes.GetNumberOfItems()):
                    node = tempFidNodes.GetItemAsObject(i)
                    if node:
                        slicer.mrmlScene.RemoveNode(node)
                tempFidNodes = slicer.mrmlScene.GetNodesByName(".tip? [Ctrl+y/n/u]")
                for i in range(tempFidNodes.GetNumberOfItems()):
                    node = tempFidNodes.GetItemAsObject(i)
                    if node:
                        slicer.mrmlScene.RemoveNode(node)
                self.tempPointList = []
                # self.labelMapNode=None
                # clear label image
                if self.labelMapNode:
                    if 0:
                        self.clearLabelMap()

    def clearLabelMap(self, label=None):
        """
        Erase the contents of the label map.
        """
        # productive
        profprint()
        widget = slicer.modules.NeedleFinderWidget
        print("clearing label map")
        # self.undoRedo.saveState()
        labelImage = self.labelMapNode.GetImageData()
        shape = list(
            labelImage.GetDimensions()
        ).reverse()  # ??? this code has no effect, shape=None !!!
        labelArray = vtk.util.numpy_support.vtk_to_numpy(
            labelImage.GetPointData().GetScalars()
        ).reshape(shape)
        if not label:
            labelArray[:] = 0
        else:
            labelArray[labelArray == label] = 0
        self.editUtil.markVolumeNodeAsModified(widget.labelMapNode)

    def processEventNeedleValidation(self, observee, event=None):
        """
        Get the mouse clicks and create a fiducial node at this position.
        """
        # productive #frequent #event-handler
        if frequent:
            profprint()
        if observee in self.sliceWidgetsPerStyle and event == "LeftButtonPressEvent":

            sliceWidget = self.sliceWidgetsPerStyle[observee]
            interactor = observee.GetInteractor()
            xy = interactor.GetEventPosition()
            xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy)
            ras = sliceWidget.sliceView().convertXYZToRAS(xyz)

            ijk = self.logic.ras2ijk(ras)

            self.logic.t0 = time.clock()
            widget = slicer.modules.NeedleFinderWidget
            widget.stepNeedle += 1
            self.logic.placeNeedleShaftEvalMarker(
                ijk,
                widget.editNeedleTxtBox.value,
                self.logic.findNextStepNumber(widget.editNeedleTxtBox.value),
            )
            self.logic.drawValidationNeedles()

    def processEventAddCTLPoints(self, observee, event=None):
        """
        Get the mouse clicks and create a fiducial node at this position.
        """
        # productive #frequent #event-handler
        if frequent:
            profprint()
        if observee in self.sliceWidgetsPerStyle and event == "LeftButtonPressEvent":

            sliceWidget = self.sliceWidgetsPerStyle[observee]
            interactor = observee.GetInteractor()
            xy = interactor.GetEventPosition()
            xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy)
            ras = sliceWidget.sliceView().convertXYZToRAS(xyz)

            needleNumber = self.logic.assignNeedle(ras)
            print("needlenumber to assign: ", needleNumber)
            if needleNumber is None:
                needleNumber = max(self.logic.findNeedles(all=1)) + 1

            ijk = self.logic.ras2ijk(ras)

            self.logic.t0 = time.clock()
            widget = slicer.modules.NeedleFinderWidget
            widget.stepNeedle += 1
            self.logic.placeNeedleShaftEvalMarker(
                ijk, needleNumber, self.logic.findNextStepNumber(needleNumber)
            )
            self.logic.drawValidationNeedles(needleNumber)

    def processEventAddObturatorNeedleTips(self, observee, event=None):
        """
        Get the mouse clicks and create a fiducial node at this position.
        """
        # productive
        profprint()
        if observee in self.sliceWidgetsPerStyle and event == "LeftButtonPressEvent":
            sliceWidget = self.sliceWidgetsPerStyle[observee]
            interactor = observee.GetInteractor()
            xy = interactor.GetEventPosition()
            xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy)
            ras = sliceWidget.sliceView().convertXYZToRAS(xyz)

            colorVar = random.randrange(50, 100, 1)  # ???/(100.)
            volumeNode = (
                slicer.app.layoutManager()
                .sliceWidget("Red")
                .sliceLogic()
                .GetBackgroundLayer()
                .GetVolumeNode()
            )
            imageData = volumeNode.GetImageData()
            spacing = volumeNode.GetSpacing()
            ijk = self.logic.ras2ijk(ras)
            self.logic.t0 = time.clock()
            self.logic.obturatorNeedle(ijk, imageData, colorVar, spacing)
            self.obtuNeedle += 1

    def processEventAddManualTips(self, observee, event=None):
        """
        Get the mouse clicks and create a fiducial node at this position. Used later for the fiducial registration
        ??? used?
        """
        # obsolete?
        profbox()
        if observee in self.sliceWidgetsPerStyle and event == "LeftButtonPressEvent":
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
                xyz = sliceWidget.sliceView().convertDeviceToXYZ(xy)
                ras = sliceWidget.sliceView().convertXYZToRAS(xyz)

            volumeNode = (
                slicer.app.layoutManager()
                .sliceWidget("Red")
                .sliceLogic()
                .GetBackgroundLayer()
                .GetVolumeNode()
            )
            imageData = volumeNode.GetImageData()
            spacing = volumeNode.GetSpacing()
            self.logic.addManualTip(ras)

    def onSave(self):
        """
        show file dialog to save parameters
        """
        # productive #onButton
        profprint()

        self.dirDialog = qt.QFileDialog(self.parent)
        self.dirDialog.setDirectory(
            slicer.modules.needlefinder.path.replace("NeedleFinder.py", "Config")
        )
        self.dirDialog.options = self.dirDialog.DontUseNativeDialog
        self.dirDialog.acceptMode = self.dirDialog.AcceptSave
        self.dirDialog.defaultSuffix = "cfg"
        self.dirDialog.setNameFilter("Configuration file (*.cfg)")
        self.dirDialog.connect("fileSelected(QString)", self.saveFileSelected)
        self.dirDialog.show()

    def saveFileSelected(self, fileName):
        """
        save parameters
        """
        # productive #callback
        profprint()
        self.logic.saveParameters(fileName)

    def onLoad(self):
        """
        show file dialogue to load parameter file
        """
        # productive #onButton
        profprint()
        self.dirDialog = qt.QFileDialog(self.parent)
        self.dirDialog.setDirectory(
            slicer.modules.needlefinder.path.replace("NeedleFinder.py", "Config")
        )
        self.dirDialog.options = self.dirDialog.DontUseNativeDialog
        self.dirDialog.acceptMode = self.dirDialog.AcceptOpen
        self.dirDialog.defaultSuffix = "cfg"
        self.dirDialog.setNameFilter("Configuration File (*.cfg)")
        self.dirDialog.connect("fileSelected(QString)", self.onLoadFileSelected)
        self.dirDialog.show()

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
        fileName = pathToScene = slicer.modules.needlefinder.path.replace(
            "NeedleFinder.py", "Config/default.cfg"
        )
        self.logic.loadParameters(fileName)
