import os.path
import unittest

import ctk
import qt
import slicer
import vtk

import Resources.utils as u
from Resources.needlefinder_logic import NeedleFinderLogic


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
        """Test:
        This utility method displays a small dialog and waits.
        This does two things: 1) it lets the event loop catch up
        to the state of the test so that rendering and widget updates
        have all taken place before the test continues and 2) it
        shows the user/developer/tester the state of the test
        so that we'll know when it breaks.
        """
        # test
        u.profprint()
        print(message)
        self.info = qt.QDialog()
        self.infoLayout = qt.QVBoxLayout()
        self.info.setLayout(self.infoLayout)
        self.label = qt.QLabel(message, self.info)
        self.infoLayout.addWidget(self.label)
        qt.QTimer.singleShot(msec, self.info.close)
        self.info.exec_()

    def setUp(self):
        """Test:
        Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        # test
        u.profprint()
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        """Test:
        Run as few or as many tests as needed here.
        """
        # test #framework #productive
        u.profprint()

        self.setUp()
        self.test_NeedleFinder1()

    def test_NeedleFinder1(self):
        """
        Unit test
        """
        # test #framework
        u.profprint()
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
        import urllib.request, urllib.error

        downloads = (
            (
                "http://slicer.kitware.com/midas3/download?items=5767",
                "FA.nrrd",
                slicer.util.loadVolume,
            ),
        )

        for url, name, loader in downloads:
            filePath = slicer.app.temporaryPath + "/" + name
            if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
                print(f"Requesting download {name} from {url}...\n")
                urllib.request.urlretrieve(url, filePath)
            if loader:
                print(f"Loading {name}...\n")
                loader(filePath)
        self.delayDisplay("Finished with download and loading\n")

        volumeNode = slicer.util.getNode(pattern="FA")
        logic = NeedleFinderLogic()
        self.assertTrue(logic.hasImageData(volumeNode))
        self.delayDisplay("Test passed!")
