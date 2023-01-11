"""**NeedleFinder Documentation**

Guillaume Pernelle,  Andre Mastmeyer, Ruibin Ma

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

import slicer

from Resources.needlefinder_logic import NeedleFinderLogic
from Resources.needlefinder_tests import NeedleFinderTest
from Resources.utils import *
from Resources.constants.settings import *


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
        parent.contributors = [
            "Guillaume Pernelle",
            "Andre Mastmeyer",
            "Ruibin Ma",
            "Alireza Mehrtash",
            "Lauren Barber",
            "Nabgha Fahrat",
            "Sandy Wells",
            "Yi Gao",
            "Antonio Damato",
            "Tina Kapur",
            "Akila Viswanathan",
        ]
        parent.helpText = "https://github.com/gpernelle/NeedleFinder/wiki"
        parent.acknowledgementText = " Version : " + "NeedleFinder 2015 v1.0."
        self.NeedleFinderWidget = 0
        self.parent = parent
        self.loaded = 0
        self.logic = NeedleFinderLogic()
        try:
            slicer.selfTests
        except AttributeError:
            slicer.selfTests = {}
        slicer.selfTests["NeedleFinder"] = self.runTest

        def __onNodeAdded__(self, caller, eventId, callData):
            """IF fiducial node, observe mvt for undo function"""
            self.logic.observeSingleFiducial(callData, eventId)

        def __onNodeRemoved__(self, caller, eventId, callData):
            """Delete observer if fiducial node removed"""
            self.logic.removeNodeObserver(caller, eventId)

        # def __onSceneLoaded__(self, caller, eventId, callData):
        #   """Load CTRL points AFTER scene finished to be loaded"""
        #   self.logic.loadCTLPointsInTable()
        #   # return 0

        def __onSceneClosed__(self, caller, eventId, callData):
            """Clean report table and internal variables"""
            self.logic.cleanTable()
            w = slicer.modules.NeedleFinderWidget
            w.initObturatorNeedles()

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




