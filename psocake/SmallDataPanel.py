import numpy as np
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.dockarea import *
from pyqtgraph.Qt import QtCore, QtGui
try:
    from PyQt5.QtWidgets import *
    using_pyqt4 = False
except ImportError:
    using_pyqt4 = True
    pass
import subprocess
import h5py, os
import pyqtgraph as pg

class SmallData(object):
    def __init__(self, parent = None):
        self.parent = parent

        ## Dock: Quantifier
        self.dock = Dock("Small Data", size=(100, 100))
        self.win = ParameterTree()
        self.dock.addWidget(self.win)
        self.winL = pg.LayoutWidget()
        self.refreshBtn = QtGui.QPushButton('Refresh')
        self.winL.addWidget(self.refreshBtn, row=0, col=0)
        self.peakogramBtn = QtGui.QPushButton('Peakogram')
        self.winL.addWidget(self.peakogramBtn, row=0, col=1)
        self.dock.addWidget(self.winL)
        # Add plot
        self.winP = pg.PlotWidget(title="Metric")
        self.dock.addWidget(self.winP)

        # Quantifier parameter tree
        self.quantifier_grp = 'Small data'
        self.quantifier_filename_str = 'filename'
        self.quantifier_dataset_str = 'dataset'
        self.quantifier_sort_str = 'sort'

        # Quantifier
        self.quantifier_filename = ''
        self.quantifier_dataset = '/entry_1/result_1/'
        self.quantifier_sort = False
        self.quantifierFileOpen = False
        self.quantifierHasData = False
        self.quantifierEvent = None

        self.params = [
            {'name': self.quantifier_grp, 'type': 'group', 'children': [
                {'name': self.quantifier_filename_str, 'type': 'str', 'value': self.quantifier_filename, 'tip': "Full path Hdf5 filename"},
                {'name': self.quantifier_dataset_str, 'type': 'str', 'value': self.quantifier_dataset, 'tip': "Hdf5 dataset metric, nPeaksAll or nHitsAll"},
                {'name': self.quantifier_sort_str, 'type': 'bool', 'value': self.quantifier_sort, 'tip': "Descending sort metric"},
            ]},
        ]

        self.pSmall = Parameter.create(name='paramsQuantifier', type='group', \
                                       children=self.params, expanded=True)
        self.win.setParameters(self.pSmall, showTop=False)
        self.pSmall.sigTreeStateChanged.connect(self.change)
        if using_pyqt4:
            self.parent.connect(self.refreshBtn, QtCore.SIGNAL("clicked()"), self.reloadQuantifier)
            self.parent.connect(self.peakogramBtn, QtCore.SIGNAL("clicked()"), self.showPeakogram)
        else:
            self.refreshBtn.clicked.connect(self.reloadQuantifier)
            self.peakogramBtn.clicked.connect(self.showPeakogram)
    # If anything changes in the parameter tree, print a message
    def change(self, panel, changes):
        for param, change, data in changes:
            path = panel.childPath(param)
            if self.parent.args.v >= 1:
                print('  path: %s' % path)
                print('  change:    %s' % change)
                print('  data:      %s' % str(data))
                print('  ----------')
            self.paramUpdate(path, change, data)

    ##############################
    # Mandatory parameter update #
    ##############################
    def paramUpdate(self, path, change, data):
        if path[0] == self.quantifier_grp:
            if path[1] == self.quantifier_filename_str:
                self.updateQuantifierFilename(data)
            elif path[1] == self.quantifier_dataset_str:
                self.updateQuantifierDataset(data)
            elif path[1] == self.quantifier_sort_str:
                self.updateQuantifierSort(data)

    ##################################
    ########### Quantifier ###########
    ##################################

    def reloadQuantifier(self):
        self.updateQuantifierFilename(self.quantifier_filename)
        self.updateQuantifierDataset(self.quantifier_dataset)

    def updateQuantifierFilename(self, data):
        self.quantifier_filename = data
        if self.parent.args.v >= 1: print("Done opening metric")

    def updateQuantifierDataset(self, data):
        self.quantifier_dataset = data
        if os.path.isfile(self.quantifier_filename):
            try:
                self.quantifierFile = h5py.File(self.quantifier_filename, 'r')
                self.quantifierMetric = self.quantifierFile[self.quantifier_dataset][()]
                try:
                    if self.quantifier_dataset[0] == '/':  # dataset starts with "/"
                        self.quantifier_eventDataset = self.quantifier_dataset.split("/")[1] + "/event"
                    else:  # dataset does not start with "/"
                        self.quantifier_eventDataset = "/" + self.quantifier_dataset.split("/")[0] + "/event"
                    self.quantifierEvent = self.quantifierFile[self.quantifier_eventDataset][()]
                except:
                    if self.parent.args.v >= 1: print("Couldn't find /event dataset")
                    self.quantifierEvent = np.arange(len(self.quantifierMetric))
                self.quantifierFile.close()
                self.quantifierInd = np.arange(len(self.quantifierMetric))
                self.updateQuantifierSort(self.quantifier_sort)
            except:
                if self.parent.args.v >= 1: print("Couldn't read metric")
                self.quantifierMetric = np.zeros((self.parent.exp.eventTotal,))
                self.quantifierInd = np.arange(len(self.quantifierMetric))
                self.updateQuantifierSort(self.quantifier_sort)
            if self.parent.args.v >= 1: print("Done reading metric")
        else:
            if self.parent.args.v >= 1: print("no file, display all zeros")
            self.quantifierMetric = np.zeros((self.parent.exp.eventTotal,))
            self.quantifierInd = np.arange(len(self.quantifierMetric))
            self.updateQuantifierSort(self.quantifier_sort)

    def updateQuantifierSort(self, data):
        self.quantifier_sort = data
        try:
            if self.quantifier_sort is True:
                self.quantifierIndSorted = np.argsort(self.quantifierMetric)[::-1]
                self.quantifierMetricSorted = self.quantifierMetric[self.quantifierIndSorted]
                #self.quantifierEventSorted = self.quantifierMetric[self.quantifierInd]
                self.updateQuantifierPlot(self.quantifierMetricSorted)
            else:
                self.updateQuantifierPlot(self.quantifierMetric)
        except:
            print("Couldn't sort data")
            pass

    def updateQuantifierPlot(self, metric):
        self.winP.getPlotItem().clear()
        if len(np.where(metric==-1)[0]) > 0:
            self.curve = self.winP.plot(metric, pen=(200, 200, 200), symbolBrush=(255, 0, 0), symbolPen='k') # red
        else: # Every event was processed
            self.curve = self.winP.plot(metric, pen=(200, 200, 200), symbolBrush=(0, 0, 255), symbolPen='k') # blue
        self.winP.setLabel('left', "Small data")
        if self.quantifier_sort:
            self.winP.setLabel('bottom', "Sorted Event Index")
        else:
            self.winP.setLabel('bottom', "Event Index")
        self.curve.curve.setClickable(True)
        self.curve.sigClicked.connect(self.clicked)

    def clicked(self, points):
        with pg.BusyCursor():
            if self.parent.args.v >= 1:
                print("curve clicked", points)
                from pprint import pprint
                pprint(vars(points.scatter))
            for i in range(len(points.scatter.data)):
                if points.scatter.ptsClicked[0] == points.scatter.data[i][9]: # tenth element contains SpotItem
                    ind = i
                    break
            indX = points.scatter.data[i][0]
            indY = points.scatter.data[i][1]
            if self.parent.args.v >= 1: print("x,y: ", indX, indY)
            if self.quantifier_sort:
                ind = self.quantifierIndSorted[ind]
            if self.quantifierEvent is None:
                self.quantifierEvent = np.arange(self.parent.exp.eventTotal)
            if self.parent.eventNumber != self.quantifierEvent[ind]:
                self.parent.eventNumber = self.quantifierEvent[ind]
                self.parent.calib, self.parent.data = self.parent.img.getDetImage(self.parent.eventNumber)
                self.parent.img.win.setImage(self.parent.data, autoRange=False, autoLevels=False, autoHistogramRange=False)
                self.parent.exp.p.param(self.parent.exp.exp_grp, self.parent.exp.exp_evt_str).setValue(self.parent.eventNumber)

    def showPeakogram(self):
        if os.path.isfile(self.quantifier_filename):
            fname = self.quantifier_filename.split(".cxi")[0]
            if self.parent.pk.tag:
                fname = fname.split("_"+self.parent.pk.tag)[0]
            c = 0
            while True:
                _fname = fname
                if self.parent.pk.tag:
                    _fname += "_" + str(c) + "_" + self.parent.pk.tag + ".cxi"
                else:
                    _fname += "_" + str(c) + ".cxi"
                exists = os.path.exists(_fname)
                if not exists: break
                c += 1
            cmd = "peakogram -i " + fname + " -n " + str(c)
            if self.parent.pk.tag: cmd += " -t " + self.parent.pk.tag
            print("Running: ", cmd)
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            print("Peakogram plot for the peak finding results for this run will pop up soon")
