import inspect
import qt
from Resources.constants.settings import *

# profiling/debugging helper functions:
def whoami():
    return inspect.stack()[1][3]


def whosdaddy():
    return inspect.stack()[2][3]


def whosgranny():
    return inspect.stack()[3][3]

def lineno():
    # Returns the current line number in our program
    return int(inspect.currentframe().f_back.f_lineno)


def pause(box=False):
    if box:
        msgbox("Pause, go to console...")
    try:
        eval(input("You can now inspect the viewers.\nPress enter to continue..."))
    except EOFError:
        pass


def msgbox(text):
    print(text)
    qt.QMessageBox.about(0, "Profiling:", text)


def assertbox(cond, msg):
    try:
        assert cond
    except:
        breakbox(msg)


def breakbox(text):
    print(text)
    dialog = qt.QDialog()
    ret = messageBox = qt.QMessageBox.question(
        dialog,
        "Profiling:",
        text + " Continue?",
        qt.QMessageBox.Ok,
        qt.QMessageBox.Cancel,
    )
    if ret != qt.QMessageBox.Ok:
        raise  # allows the debugger to start when attached and exceptions are caught


def profprint(className=""):
    if profiling:
        profString = f"{className}.{whosdaddy()} -----------------------"
        print(profString)
        if loggingInfos:
            try:
                with open("/tmp/debug.log", "a") as myfile:
                    myfile.write(profString + "\n")
            except:
                pass


def logprint(className="", msg=""):
    if loggingInfos:
        msg += f" from {className}.{whosdaddy()}"
        try:
            with open("/tmp/debug.log", "a") as myfile:
                myfile.write(msg + "\n")
        except:
            pass


def profbox(className=""):
    if profiling:
        strg = f"{className}.{whosdaddy()} -----------------------"
        print(strg)
        msgbox(strg)


def getClassName(self):
    return self.__class__.__name__
