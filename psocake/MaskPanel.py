import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import h5py
try:
    from PyQt5.QtWidgets import *
    using_pyqt4 = False
except ImportError:
    using_pyqt4 = True
    pass
from pyqtgraph.parametertree import Parameter, ParameterTree
from pyqtgraph.dockarea import *

from PSCalib.GeometryObject import two2x1ToData2x2
import psocake.colorScheme as color
from psocake import LaunchPowderProducer
from psocake import utils
from psocake import myskbeam

class MaskMaker(object):
    def __init__(self, parent = None):
        self.parent = parent

        ## Dock: Mask Panel
        self.dock = Dock("Mask Panel", size=(1, 1))
        self.win = ParameterTree()
        self.dock.addWidget(self.win)
        self.winL = pg.LayoutWidget()
        self.maskRectBtn = QtGui.QPushButton('Stamp rectangular mask')
        self.winL.addWidget(self.maskRectBtn, row=0, col=0)#, colspan=2)
        self.maskCircleBtn = QtGui.QPushButton('Stamp circular mask')
        self.winL.addWidget(self.maskCircleBtn, row=0, col=1)#, colspan=2)
        self.maskThreshBtn = QtGui.QPushButton('Mask outside histogram')
        self.winL.addWidget(self.maskThreshBtn, row=1, col=1)#, colspan=2)
        self.maskPolyBtn = QtGui.QPushButton('Stamp polygon mask')
        self.winL.addWidget(self.maskPolyBtn, row=1, col=0)#, colspan=2)
        self.deployMaskBtn = QtGui.QPushButton()
        self.deployMaskBtn.setStyleSheet('QPushButton {background-color: #A3C1DA; color: red;}')
        self.deployMaskBtn.setText('Save static mask')
        self.winL.addWidget(self.deployMaskBtn, row=2, col=0)
        self.loadMaskBtn = QtGui.QPushButton()
        self.loadMaskBtn.setStyleSheet('QPushButton {background-color: #A3C1DA; color: red;}')
        self.loadMaskBtn.setText('Load mask')
        self.winL.addWidget(self.loadMaskBtn, row=2, col=1)
        self.generatePowderBtn = QtGui.QPushButton('Generate Average Image')
        self.winL.addWidget(self.generatePowderBtn, row=3, col=0, colspan=2)
        # Connect listeners to functions
        self.dock.addWidget(self.winL)

        self.mask_grp = 'Mask'
        self.mask_mode_str = 'Masking mode'
        self.do_nothing_str = 'Off'
        self.do_toggle_str = 'Toggle'
        self.do_mask_str = 'Mask'
        self.do_unmask_str = 'Unmask'
        self.streak_mask_str = 'Use jet streak mask'
        self.streak_width_str = 'maximum streak length'
        self.streak_sigma_str = 'sigma'
        self.psana_mask_str = 'Use psana mask'
        self.user_mask_str = 'Use user-defined mask'
        self.mask_calib_str = 'calib pixels'
        self.mask_status_str = 'status pixels'
        self.mask_edges_str = 'edge pixels'
        self.mask_central_str = 'central pixels'
        self.mask_unbond_str = 'unbonded pixels'
        self.mask_unbondnrs_str = 'unbonded pixel neighbors'
        self.mask_tag_str = 'Tag'
        self.powder_grp = 'Generate Average Image'
        self.powder_outDir_str = 'Output directory'
        self.powder_runs_str = 'Run(s)'
        self.powder_queue_str = 'Queue'
        self.powder_cpu_str = 'CPUs'
        self.powder_noe_str = 'Number of events to process'
        self.powder_threshold_str = 'Threshold'
        self.masking_mode_message = "<span style='color: " + color.maskInfo + "; font-size: 24pt;'>Masking mode <br> </span>"

        ######################
        # Mask
        ######################
        self.maskingMode = 0
        self.userMaskOn = False
        self.streakMaskOn = False
        self.streak_sigma = 1
        self.streak_width = 250
        self.psanaMaskOn = True
        self.mask_calibOn = True
        self.mask_statusOn = True
        self.mask_edgesOn = True
        self.mask_centralOn = True
        self.mask_unbondOn = True
        self.mask_unbondnrsOn = True
        self.mask_tag = ''
        self.display_data = None
        self.mask_rect = None
        self.mask_circle = None
        self.mask_poly = None
        self.powder_outDir = self.parent.psocakeDir
        self.powder_runs = ''
        self.powder_queue = self.parent.pk.hitParam_psanaq_str
        self.powder_cpus = 24
        self.powder_noe = -1
        self.powder_threshold = -1

        ###########################
        # Mask variables
        ###########################
        self.psanaMask = True # psana mask
        self.psanaMaskAssem = None
        self.userMask = None # user-defined mask
        self.userMaskAssem = None
        self.streakMask = None # jet streak mask
        self.StreakMask = None # streak mask class
        self.streakMaskAssem = None
        self.combinedMask = None # combined mask
        self.gapAssemInd = None

        self.params = [
            {'name': self.mask_grp, 'type': 'group', 'children': [
                {'name': self.user_mask_str, 'type': 'bool', 'value': self.userMaskOn, 'tip': "Mask areas defined by user", 'children':[
                    {'name': self.mask_mode_str, 'type': 'list', 'values': {self.do_toggle_str: 3,
                                                                            self.do_unmask_str: 2,
                                                                            self.do_mask_str: 1,
                                                                            self.do_nothing_str: 0},
                                                                       'value': self.maskingMode,
                                                                       'tip': "Choose masking mode"},
                ]},
                {'name': self.streak_mask_str, 'type': 'bool', 'value': self.streakMaskOn, 'tip': "Mask jet streaks shot-to-shot", 'children':[
                    {'name': self.streak_width_str, 'type': 'float', 'value': self.streak_width, 'tip': "set maximum length of streak"},
                    {'name': self.streak_sigma_str, 'type': 'float', 'value': self.streak_sigma, 'tip': "set number of sigma to threshold"},
                ]},
                {'name': self.psana_mask_str, 'type': 'bool', 'value': self.psanaMaskOn, 'tip': "Mask edges and unbonded pixels etc", 'children': [
                    {'name': self.mask_calib_str, 'type': 'bool', 'value': self.mask_calibOn, 'tip': "use custom mask deployed in calibdir"},
                    {'name': self.mask_status_str, 'type': 'bool', 'value': self.mask_statusOn, 'tip': "mask bad pixel status"},
                    {'name': self.mask_edges_str, 'type': 'bool', 'value': self.mask_edgesOn, 'tip': "mask edge pixels"},
                    {'name': self.mask_central_str, 'type': 'bool', 'value': self.mask_centralOn, 'tip': "mask central edge pixels inside asic2x1"},
                    {'name': self.mask_unbond_str, 'type': 'bool', 'value': self.mask_unbondOn, 'tip': "mask unbonded pixels (cspad only)"},
                    {'name': self.mask_unbondnrs_str, 'type': 'bool', 'value': self.mask_unbondnrsOn, 'tip': "mask unbonded pixel neighbors (cspad only)"},
                    #{'name': self.mask_generous_str, 'type': 'bool', 'value': self.mask_generousOn, 'tip': "mask bad readout channels"},
                ]},
                {'name': self.mask_tag_str, 'type': 'str', 'value': self.mask_tag, 'tip': "attach tag to mask, e.g. staticMask_tag.h5"},
            ]},
            {'name': self.powder_grp, 'type': 'group', 'children': [
                {'name': self.powder_outDir_str, 'type': 'str', 'value': self.powder_outDir},
                {'name': self.powder_runs_str, 'type': 'str', 'value': self.powder_runs,
                 'tip': "comma separated or use colon for a range, e.g. 1,3,5:7 = runs 1,3,5,6,7"},
                {'name': self.powder_queue_str, 'type': 'list', 'values': {self.parent.pk.hitParam_psfehhiprioq_str: 'psfehhiprioq',
                                                                           self.parent.pk.hitParam_psnehhiprioq_str: 'psnehhiprioq',
                                                                           self.parent.pk.hitParam_psfehprioq_str: 'psfehprioq',
                                                                           self.parent.pk.hitParam_psnehprioq_str: 'psnehprioq',
                                                                           self.parent.pk.hitParam_psfehq_str: 'psfehq',
                                                                           self.parent.pk.hitParam_psnehq_str: 'psnehq',
                                                                           self.parent.pk.hitParam_psanaq_str: 'psanaq',
                                                                           self.parent.pk.hitParam_psdebugq_str: 'psdebugq',
                                                                           self.parent.pk.hitParam_psanagpuq_str: 'psanagpuq',
                                                                           self.parent.pk.hitParam_psanaidleq_str: 'psanaidleq',
                                                                           self.parent.pk.hitParam_ffbh1q_str: 'ffbh1q',
                                                                           self.parent.pk.hitParam_ffbl1q_str: 'ffbl1q',
                                                                           self.parent.pk.hitParam_ffbh2q_str: 'ffbh2q',
                                                                           self.parent.pk.hitParam_ffbl2q_str: 'ffbl2q',
                                                                           self.parent.pk.hitParam_ffbh3q_str: 'ffbh3q',
                                                                           self.parent.pk.hitParam_ffbl3q_str: 'ffbl3q',
                                                                           self.parent.pk.hitParam_anaq_str: 'anaq'
                                                                           },
                 'value': self.powder_queue, 'tip': "Choose queue"},
                {'name': self.powder_cpu_str, 'type': 'int', 'value': self.powder_cpus, 'tip': "number of cpus to use per run"},
                {'name': self.powder_threshold_str, 'type': 'float', 'value': self.powder_threshold, 'tip': "ignore pixels below ADU threshold, default=-1 means no threshold"},
                {'name': self.powder_noe_str, 'type': 'int', 'decimals': 7, 'value': self.powder_noe, 'tip': "number of events to process, default=-1 means process all events"},
            ]},
        ]

        self.p6 = Parameter.create(name='paramsMask', type='group', \
                                   children=self.params, expanded=True)
        self.win.setParameters(self.p6, showTop=False)
        self.p6.sigTreeStateChanged.connect(self.change)

        if using_pyqt4:
            self.parent.connect(self.maskRectBtn, QtCore.SIGNAL("clicked()"), self.makeMaskRect)
            self.parent.connect(self.maskCircleBtn, QtCore.SIGNAL("clicked()"), self.makeMaskCircle)
            self.parent.connect(self.maskThreshBtn, QtCore.SIGNAL("clicked()"), self.makeMaskThresh)
            self.parent.connect(self.maskPolyBtn, QtCore.SIGNAL("clicked()"), self.makeMaskPoly)
            self.parent.connect(self.deployMaskBtn, QtCore.SIGNAL("clicked()"), self.deployMask)
            self.parent.connect(self.loadMaskBtn, QtCore.SIGNAL("clicked()"), self.loadMask)
            self.parent.connect(self.generatePowderBtn, QtCore.SIGNAL("clicked()"), self.makePowder)
        else:
            self.maskRectBtn.clicked.connect(self.makeMaskRect)
            self.maskCircleBtn.clicked.connect(self.makeMaskCircle)
            self.maskThreshBtn.clicked.connect(self.makeMaskThresh)
            self.maskPolyBtn.clicked.connect(self.makeMaskPoly)
            self.deployMaskBtn.clicked.connect(self.deployMask)
            self.loadMaskBtn.clicked.connect(self.loadMask)
            self.generatePowderBtn.clicked.connect(self.makePowder)

    def makePowder(self):
        self.parent.thread.append(LaunchPowderProducer.PowderProducer(self.parent))  # send parent parameters with self
        self.parent.thread[self.parent.threadCounter].computePowder(self.parent.experimentName,
                                                                    self.parent.runNumber,
                                                                    self.parent.detInfo)
        self.parent.threadCounter += 1

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
        if path[0] == self.mask_grp:
            if path[1] == self.user_mask_str and len(path) == 2:
                self.updateUserMask(data)
                self.parent.pk.algInitDone = False
            elif path[1] == self.streak_mask_str and len(path) == 2:
                self.updateStreakMask(data)
                self.parent.pk.algInitDone = False
            elif path[1] == self.psana_mask_str and len(path) == 2:
                self.updatePsanaMask(data)
                self.parent.pk.algInitDone = False
            elif path[1] == self.mask_tag_str and len(path) == 2:
                self.updateMaskTag(data)
            if len(path) == 3:
                if path[2] == self.mask_mode_str:
                    self.parent.pk.algInitDone = False
                    self.updateMaskingMode(data)
                if path[2] == self.streak_width_str:
                    self.parent.pk.algInitDone = False
                    self.updateStreakWidth(data)
                if path[2] == self.streak_sigma_str:
                    self.parent.pk.algInitDone = False
                    self.updateStreakSigma(data)
                if path[2] == self.mask_calib_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                elif path[2] == self.mask_status_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                elif path[2] == self.mask_edges_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                elif path[2] == self.mask_central_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                elif path[2] == self.mask_unbond_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                elif path[2] == self.mask_unbondnrs_str:
                    self.parent.pk.algInitDone = False
                    self.updatePsanaMaskFlag(path[2], data)
                #elif path[2] == self.mask_generous_str:
                #    self.parent.pk.algInitDone = False
                #    self.updatePsanaMaskFlag(path[2], data)
        elif path[0] == self.powder_grp:
            if path[1] == self.powder_outDir_str:
                self.powder_outDir = data
            elif path[1] == self.powder_runs_str:
                self.powder_runs = data
            elif path[1] == self.powder_queue_str:
                self.powder_queue = data
            elif path[1] == self.powder_cpu_str:
                self.powder_cpus = data
            elif path[1] == self.powder_noe_str:
                self.powder_noe = data
            elif path[1] == self.powder_threshold_str:
                self.powder_threshold = data

    ##################################
    ############ Masking #############
    ##################################

    def resetMasks(self):
        self.userMask = None
        self.psanaMask = None
        self.streakMask = None
        self.StreakMask = None
        self.userMaskAssem = None
        self.psanaMaskAssem = None
        self.streakMaskAssem = None
        self.combinedMask = None
        self.gapAssemInd = None
        self.gapAssem = None
        self.userMaskOn = False
        self.psanaMaskOn = True
        self.streakMaskOn = False
        self.maskingMode = 0
        self.p6.param(self.mask_grp, self.user_mask_str, self.mask_mode_str).setValue(0)
        self.p6.param(self.mask_grp, self.user_mask_str).setValue(0)
        self.p6.param(self.mask_grp, self.psana_mask_str).setValue(1)
        self.p6.param(self.mask_grp, self.streak_mask_str).setValue(0)

    def updateUserMask(self, data):
        self.userMaskOn = data
        self.parent.pk.algInitDone = False
        self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done updateUserMask: ", self.userMaskOn)

    def updateStreakMask(self, data):
        self.streakMaskOn = data
        self.parent.pk.algInitDone = False
        self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done updateStreakMask: ", self.streakMaskOn)

    def updateStreakWidth(self, data):
        self.streak_width = data
        self.streakMask = None
        self.initMask()
        self.parent.pk.algInitDone = False
        self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done updateStreakWidth: ", self.streak_width)

    def updateStreakSigma(self, data):
        self.streak_sigma = data
        self.streakMask = None
        self.initMask()
        self.parent.pk.algInitDone = False
        self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done updateStreakSigma: ", self.streak_sigma)

    def updatePsanaMask(self, data):
        self.psanaMaskOn = data
        self.parent.pk.algInitDone = False
        self.updatePsanaMaskOn()
        if self.parent.args.v >= 1: print("Done updatePsanaMask: ", self.psanaMaskOn)

    def updateMaskingMode(self, data):
        self.maskingMode = data
        if self.maskingMode == 0:
            # display text
            self.parent.label.setText("")
            # do not display user mask
            self.displayMask()
            # remove ROIs
            self.parent.img.win.getView().removeItem(self.mask_rect)
            self.parent.img.win.getView().removeItem(self.mask_circle)
            self.parent.img.win.getView().removeItem(self.mask_poly)
        else:
            # display text
            self.parent.label.setText(self.masking_mode_message)
            # display user mask
            self.displayMask()
            # init masks
            if self.mask_rect is None:
                # Rect mask
                self.mask_rect = pg.ROI(pos=[-300, 0], size=[200, 200], snapSize=1.0, scaleSnap=True, translateSnap=True,
                                        pen={'color': 'r', 'width': 4})
                self.mask_rect.addScaleHandle([1, 0.5], [0.5, 0.5])
                self.mask_rect.addScaleHandle([0.5, 0], [0.5, 0.5])
                self.mask_rect.addScaleHandle([0.5, 1], [0.5, 0.5])
                self.mask_rect.addScaleHandle([0, 0.5], [0.5, 0.5])
                self.mask_rect.addScaleHandle([0, 0], [1, 1])  # bottom,left handles scaling both vertically and horizontally
                self.mask_rect.addScaleHandle([1, 1], [0, 0])  # top,right handles scaling both vertically and horizontally
                self.mask_rect.addScaleHandle([1, 0], [0, 1])  # bottom,right handles scaling both vertically and horizontally
                self.mask_rect.addScaleHandle([0, 1], [1, 0])
                # Circular mask
                self.mask_circle = pg.CircleROI([-300, 600], size=[200, 200], snapSize=1.0, scaleSnap=True,
                                                translateSnap=True, pen={'color': 'r', 'width': 4})
                self.mask_circle.addScaleHandle([0.1415, 0.707 * 1.2], [0.5, 0.5])
                self.mask_circle.addScaleHandle([0.707 * 1.2, 0.1415], [0.5, 0.5])
                self.mask_circle.addScaleHandle([0.1415, 0.1415], [0.5, 0.5])
                #self.mask_circle.addScaleHandle([0, 0.5], [0.5, 0.5]) # west: pyqtgraph error
                self.mask_circle.addScaleHandle([0.5, 0.0], [0.5, 0.5]) # south
                self.mask_circle.addScaleHandle([0.5, 1.0], [0.5, 0.5]) # north
                #self.mask_circle.addScaleHandle([1.0, 0.5], [0.5, 0.5]) # east: pyqtgraph error
                # Polygon mask
                self.mask_poly = pg.PolyLineROI([[-300, 300], [-300,500], [-100,500],
                                                 [-100,400], [-225,400], [-225,300]],
                                                closed=True, snapSize=1.0, scaleSnap=True, translateSnap=True,
                                                pen={'color': 'r', 'width': 4})

            # add ROIs
            self.parent.img.win.getView().addItem(self.mask_rect)
            self.parent.img.win.getView().addItem(self.mask_circle)
            self.parent.img.win.getView().addItem(self.mask_poly)
        if self.parent.args.v >= 1: print("Done updateMaskingMode: ", self.maskingMode)

    def updatePsanaMaskFlag(self, flag, data):
        if flag == self.mask_calib_str:
            self.mask_calibOn = data
        elif flag == self.mask_status_str:
            self.mask_statusOn = data
        elif flag == self.mask_central_str:
            self.mask_centralOn = data
        elif flag == self.mask_edges_str:
            self.mask_edgesOn = data
        elif flag == self.mask_unbond_str:
            self.mask_unbondOn = data
        elif flag == self.mask_unbondnrs_str:
            self.mask_unbondnrsOn = data
        self.updatePsanaMaskOn()

    def updatePsanaMaskOn(self):
        if self.parent.det is not None:
            self.initMask()
            self.psanaMask = self.parent.det.mask(self.parent.evt, calib=self.mask_calibOn, status=self.mask_statusOn,
                                           edges=self.mask_edgesOn, central=self.mask_centralOn,
                                           unbond=self.mask_unbondOn, unbondnbrs=self.mask_unbondnrsOn)
            if self.psanaMask is not None:
                self.psanaMaskAssem = self.parent.det.image(self.parent.evt, self.psanaMask)
            else:
                self.psanaMaskAssem = None
            self.parent.pk.updateClassification()
            try:
                self.parent.labeling.removeLabels(clearAll = False)
                self.parent.labeling.updateAlgorithm()
                self.parent.labeling.drawLabels()
            except AttributeError:
                pass

    def updateMaskTag(self, data):
        self.mask_tag = data

    def initMask(self):
        if self.parent.det is not None:
            if self.gapAssemInd is None:
                self.gapAssem = self.parent.det.image(self.parent.evt, np.ones_like(self.parent.exp.detGuaranteed,dtype='int'))
                self.gapAssemInd = np.where(self.gapAssem==0)
            if self.userMask is None and self.parent.data is not None:
                # initialize
                self.userMaskAssem = np.ones_like(self.parent.data,dtype='int')
                self.userMask = self.parent.det.ndarray_from_image(self.parent.evt,self.userMaskAssem, pix_scale_size_um=None, xy0_off_pix=None)
            if self.streakMask is None:
                self.StreakMask = myskbeam.StreakMask(self.parent.det, self.parent.evt, width=self.streak_width, sigma=self.streak_sigma)
        if self.parent.args.v >= 1: print("Done initMask")

    def displayMask(self):
        # convert to RGB
        if self.userMaskOn is False and self.streakMaskOn is False and self.psanaMaskOn is False:
            self.display_data = self.parent.data
        elif self.userMaskAssem is None and self.streakMaskAssem is None and self.psanaMaskAssem is None:
            self.display_data = self.parent.data
        elif self.parent.data is not None:
            self.display_data = np.zeros((self.parent.data.shape[0], self.parent.data.shape[1], 3), dtype = self.parent.data.dtype)
            self.display_data[:,:,0] = self.parent.data
            self.display_data[:,:,1] = self.parent.data
            self.display_data[:,:,2] = self.parent.data
            # update streak mask as red
            if self.streakMaskOn is True and self.streakMaskAssem is not None:
                self.streakMaskAssem[self.gapAssemInd] = 1
                _streakMaskInd = np.where(self.streakMaskAssem==0)
                self.display_data[_streakMaskInd[0], _streakMaskInd[1], 0] = self.parent.data[_streakMaskInd] + (np.max(self.parent.data) - self.parent.data[_streakMaskInd]) * (1-self.streakMaskAssem[_streakMaskInd])
                self.display_data[_streakMaskInd[0], _streakMaskInd[1], 1] = self.parent.data[_streakMaskInd] * self.streakMaskAssem[_streakMaskInd]
                self.display_data[_streakMaskInd[0], _streakMaskInd[1], 2] = self.parent.data[_streakMaskInd] * self.streakMaskAssem[_streakMaskInd]
            # update psana mask as green
            if self.psanaMaskOn is True and self.psanaMaskAssem is not None:
                self.psanaMaskAssem[self.gapAssemInd] = 1
                _psanaMaskInd = np.where(self.psanaMaskAssem==0)
                self.display_data[_psanaMaskInd[0], _psanaMaskInd[1], 0] = self.parent.data[_psanaMaskInd] * self.psanaMaskAssem[_psanaMaskInd]
                self.display_data[_psanaMaskInd[0], _psanaMaskInd[1], 1] = self.parent.data[_psanaMaskInd] + (np.max(self.parent.data) - self.parent.data[_psanaMaskInd]) * (1-self.psanaMaskAssem[_psanaMaskInd])
                self.display_data[_psanaMaskInd[0], _psanaMaskInd[1], 2] = self.parent.data[_psanaMaskInd] * self.psanaMaskAssem[_psanaMaskInd]
            # update user mask as blue
            if self.userMaskOn is True and self.userMaskAssem is not None:
                self.userMaskAssem[self.gapAssemInd] = 1
                _userMaskInd = np.where(self.userMaskAssem==0)
                self.display_data[_userMaskInd[0], _userMaskInd[1], 2] = self.parent.data[_userMaskInd] * self.userMaskAssem[_userMaskInd]
                self.display_data[_userMaskInd[0], _userMaskInd[1], 1] = self.parent.data[_userMaskInd] * self.userMaskAssem[_userMaskInd]
                self.display_data[_userMaskInd[0], _userMaskInd[1], 0] = self.parent.data[_userMaskInd] + (np.max(self.parent.data) - self.parent.data[_userMaskInd]) * (1-self.userMaskAssem[_userMaskInd])
        if self.display_data is not None:
            self.parent.img.win.setImage(self.display_data, autoRange=False, autoLevels=False, autoHistogramRange=False)
        if self.parent.args.v >= 1: print("Done displayMask")

    # mask
    def makeMaskRect(self):
        self.initMask()
        if self.parent.data is not None and self.maskingMode > 0:
            selected, coord = self.mask_rect.getArrayRegion(self.parent.data, self.parent.img.win.getImageItem(), returnMappedCoords=True)
            # Remove mask elements outside data
            coord_row = coord[0, (coord[0] >= 0) & (coord[0] < self.parent.data.shape[0]) & (coord[1] >= 0) & (
            coord[1] < self.parent.data.shape[1])].ravel()
            coord_col = coord[1, (coord[0] >= 0) & (coord[0] < self.parent.data.shape[0]) & (coord[1] >= 0) & (
            coord[1] < self.parent.data.shape[1])].ravel()
            _mask = np.ones_like(self.parent.data, dtype='int')
            _mask[coord_row.astype('int'), coord_col.astype('int')] = 0
            if self.maskingMode == 1:  # masking mode
                self.userMaskAssem *= _mask
            elif self.maskingMode == 2:  # unmasking mode
                self.userMaskAssem[coord_row.astype('int'), coord_col.astype('int')] = 1
            elif self.maskingMode == 3:  # toggle mode
                self.userMaskAssem[coord_row.astype('int'), coord_col.astype('int')] = (
                1 - self.userMaskAssem[coord_row.astype('int'), coord_col.astype('int')])

            # update userMask
            self.userMask = self.parent.det.ndarray_from_image(self.parent.evt, self.userMaskAssem, pix_scale_size_um=None,
                                                                xy0_off_pix=None)

            self.displayMask()
            self.parent.pk.algInitDone = False
            self.parent.mk.combinedMask = self.getCombinedStaticMask()
            self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done makeMaskRect!!!!!!")

    def makeMaskCircle(self):
        self.initMask()
        if self.parent.data is not None and self.maskingMode > 0:
            (radiusX, radiusY) = self.mask_circle.size()
            (cornerY, cornerX) = self.mask_circle.pos()
            i0, j0 = np.meshgrid(range(int(radiusY)),
                                 range(int(radiusX)), indexing='ij')
            r = np.sqrt(np.square((i0 - radiusY / 2).astype(np.float)) +
                        np.square((j0 - radiusX / 2).astype(np.float)))
            i0 = np.rint(i0[np.where(r < radiusY / 2.)] + cornerY).astype(np.int)
            j0 = np.rint(j0[np.where(r < radiusX / 2.)] + cornerX).astype(np.int)
            i01 = i0[(i0 >= 0) & (i0 < self.parent.data.shape[1]) & (j0 >= 0) & (j0 < self.parent.data.shape[0])]
            j01 = j0[(i0 >= 0) & (i0 < self.parent.data.shape[1]) & (j0 >= 0) & (j0 < self.parent.data.shape[0])]

            _mask = np.ones_like(self.parent.data, dtype='int')
            _mask[j01, i01] = 0
            if self.maskingMode == 1:  # masking mode
                self.userMaskAssem *= _mask
            elif self.maskingMode == 2:  # unmasking mode
                self.userMaskAssem[j01, i01] = 1
            elif self.maskingMode == 3:  # toggle mode
                self.userMaskAssem[j01, i01] = (1 - self.userMaskAssem[j01, i01])

            # update userMask
            self.userMask = self.parent.det.ndarray_from_image(self.parent.evt, self.userMaskAssem, pix_scale_size_um=None,
                                                                xy0_off_pix=None)

            self.displayMask()
            self.parent.pk.algInitDone = False
            self.parent.mk.combinedMask = self.getCombinedStaticMask()
            self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done makeMaskCircle!!!!!!")

    def makeMaskThresh(self):
        self.initMask()
        if self.parent.data is not None and self.maskingMode > 0:
            histLevels = self.parent.img.win.getHistogramWidget().item.getLevels()
            _mask = np.ones_like(self.parent.data, dtype='int')
            _mask[np.where(self.parent.data < histLevels[0])] = 0
            _mask[np.where(self.parent.data > histLevels[1])] = 0
            if self.maskingMode == 1:  # masking mode
                self.userMaskAssem *= _mask
            elif self.maskingMode == 2:  # unmasking mode
                self.userMaskAssem[np.where(_mask == 0)] = 1
            elif self.maskingMode == 3:  # toggle mode
                print("You can only mask/unmask based on threshold ")

            # update userMask
            self.userMask = self.parent.det.ndarray_from_image(self.parent.evt, self.userMaskAssem, pix_scale_size_um=None,
                                                                xy0_off_pix=None)

            self.displayMask()
            self.parent.pk.algInitDone = False
            self.parent.mk.combinedMask = self.getCombinedStaticMask()
            self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done makeMaskThresh!!!!!!")

    def makeMaskPoly(self):
        self.initMask()
        if self.parent.data is not None and self.maskingMode > 0:
            calib = np.ones_like(self.parent.calib)
            img = self.parent.det.image(self.parent.evt, calib)

            self.selected = self.mask_poly.getArrayRegion(img, self.parent.img.win.getImageItem()) #, returnMappedCoords=True)

            self.selected = 1 - self.selected

            y = int(self.mask_poly.parentBounds().x())
            x = int(self.mask_poly.parentBounds().y())

            # _mask is size of img padded by selected
            _mask = np.ones((img.shape[0]+2*self.selected.shape[0],img.shape[1]+2*self.selected.shape[1]), dtype='int')
            # transfer selected onto _mask
            _mask[x+ self.selected.shape[0]:x + 2*self.selected.shape[0], y+ self.selected.shape[1]:y + 2*self.selected.shape[1]] = self.selected
            # remove padding
            _mask = _mask[self.selected.shape[0]:self.selected.shape[0]+img.shape[0], self.selected.shape[1]:self.selected.shape[1]+img.shape[1]]

            if self.maskingMode >= 1:  # masking mode
                self.userMaskAssem *= _mask

            # update userMask
            self.userMask = self.parent.det.ndarray_from_image(self.parent.evt, self.userMaskAssem, pix_scale_size_um=None,
                                                                xy0_off_pix=None)
            #
            self.displayMask()
            self.parent.pk.algInitDone = False
            self.parent.mk.combinedMask = self.getCombinedStaticMask()
            self.parent.pk.updateClassification()
        if self.parent.args.v >= 1: print("Done makeMaskPoly!!!!!!")

    def getCombinedStaticMask(self):
        # update combined mask
        combinedStaticMask = np.ones_like(self.parent.calib, dtype='int')
        if self.userMask is not None and self.userMaskOn is True:
            combinedStaticMask *= self.userMask.astype('int')
        if self.psanaMask is not None and self.psanaMaskOn is True:
            combinedStaticMask *= self.psanaMask.astype('int')
        return combinedStaticMask

    def parseMaskTag(self):
        _tag = ''
        if self.mask_tag:
            if "$n" in self.mask_tag:
                _tag = "_" + self.mask_tag.replace("$n", str(self.parent.eventNumber))
            else:
                _tag = "_" + self.mask_tag
        return _tag

    def saveCheetahStaticMask(self):
        dim0,dim1 = self.parent.detDesc.tileDim
        _tag = self.parseMaskTag()
        fname = self.parent.psocakeRunDir + "/staticMask"+_tag+".h5"
        print("Saving Cheetah static mask in: ", fname)
        myHdf5 = h5py.File(fname, 'w')
        dset = myHdf5.create_dataset('/entry_1/data_1/mask', (dim0, dim1), dtype='int')

        # Convert calib image to cheetah image
        if self.parent.mk.combinedMask is None:
            img = np.ones((dim0, dim1))
        else:
            img = self.parent.detDesc.pct(self.parent.mk.combinedMask)
        dset[:, :] = img

        # Set OM compatible dset
        myHdf5["/data/data"] = h5py.SoftLink("/entry_1/data_1/mask")

        myHdf5.close()

    def deployMask(self):
        combinedStaticMask = self.getCombinedStaticMask()

        if self.parent.args.v >= 1: print("natural static mask: ", combinedStaticMask.shape)

        if combinedStaticMask is not None:
            _tag = self.parseMaskTag()
            print("*** deploy user-defined mask as mask"+_tag+".txt and mask"+_tag+".npy as DAQ shape ***")
            print("*** deploy user-defined mask as mask_natural_shape"+_tag+".npy as natural shape ***")

            if combinedStaticMask.size == 2 * 185 * 388:  # cspad2x2
                # DAQ shape
                asData2x2 = two2x1ToData2x2(combinedStaticMask)
                np.save(self.parent.psocakeRunDir + "/mask"+_tag+".npy", asData2x2)
                np.savetxt(self.parent.psocakeRunDir + "/mask"+_tag+".txt",
                           asData2x2.reshape((-1, asData2x2.shape[-1])), fmt='%0.18e')
                # Natural shape
                np.save(self.parent.psocakeRunDir + "/mask_natural_shape"+_tag+".npy", combinedStaticMask)
            else:
                np.save(self.parent.psocakeRunDir + "/mask"+_tag+".npy", combinedStaticMask)
                np.savetxt(self.parent.psocakeRunDir + "/mask"+_tag+".txt",
                           combinedStaticMask.reshape((-1, combinedStaticMask.shape[-1])), fmt='%0.18e')
            self.saveCheetahStaticMask()

    def loadMask(self):
        fname = str(QtGui.QFileDialog.getOpenFileName(self.parent, 'Open file', self.parent.psocakeRunDir,
                                                          'ndarray image (*.npy *.npz)')[0])
        self.initMask()
        self.userMask = np.load(fname)
        if self.userMask.shape != self.parent.calib.shape:
            self.userMask = None
        if self.userMask is not None:
            self.userMaskAssem = self.parent.det.image(self.parent.evt, self.userMask)
        else:
            self.userMaskAssem = None
        self.userMaskOn = True
        self.p6.param(self.mask_grp, self.user_mask_str).setValue(self.userMaskOn)
        #self.parent.pk.updateClassification()
