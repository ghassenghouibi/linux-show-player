# -*- coding: utf-8 -*-
#
# This file is part of Linux Show Player
#
# Copyright 2012-2016 Francesco Ceruti <ceppofrancy@gmail.com>
#
# Linux Show Player is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Linux Show Player is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linux Show Player.  If not, see <http://www.gnu.org/licenses/>.
from PyQt5.QtCore import Qt, QT_TRANSLATE_NOOP
from PyQt5.QtWidgets import QVBoxLayout, QGroupBox, QHBoxLayout, QCheckBox

from lisp.application import Application
from lisp.core.has_properties import Property
from lisp.cues.cue import Cue, CueState, CueAction
from lisp.ui.settings.cue_settings import CueSettingsRegistry
from lisp.ui.settings.settings_page import SettingsPage
from lisp.ui.ui_utils import translate


class StopAll(Cue):
    Name = QT_TRANSLATE_NOOP('CueName', 'Stop-All')

    pause_mode = Property(default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = translate('CueName', self.Name)

    @Cue.state.getter
    def state(self):
        return CueState.Stop

    def __start__(self):
        cue_action = CueAction.Pause if self.pause_mode else CueAction.Stop

        for cue in Application().cue_model:
            cue.execute(action=cue_action)


class StopAllSettings(SettingsPage):
    Name = QT_TRANSLATE_NOOP('SettingsPageName', 'Cue Settings')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setLayout(QVBoxLayout())
        self.layout().setAlignment(Qt.AlignTop)

        self.group = QGroupBox(self)
        self.group.setLayout(QHBoxLayout(self.group))
        self.layout().addWidget(self.group)

        self.pauseMode = QCheckBox(self.group)
        self.group.layout().addWidget(self.pauseMode)

        self.retranslateUi()

    def retranslateUi(self):
        self.group.setTitle(translate('StopAll', 'Mode'))
        self.pauseMode.setText(translate('StopAll', 'Pause mode'))

    def enable_check(self, enabled):
        self.group.setCheckable(enabled)
        self.group.setChecked(False)

    def get_settings(self):
        conf = {}

        if not (self.group.isCheckable() and not self.group.isChecked()):
            conf['pause_mode'] = self.pauseMode.isChecked()

        return conf

    def load_settings(self, settings):
        if 'pause_mode' in settings:
            self.pauseMode.setChecked(settings['pause_mode'])


CueSettingsRegistry().add_item(StopAllSettings, StopAll)
