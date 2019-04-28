# This file is part of Linux Show Player
#
# Copyright 2018 Francesco Ceruti <ceppofrancy@gmail.com>
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

import json
import logging
from PyQt5.QtWidgets import QDialog, qApp
from os.path import exists, dirname

from lisp import layout
from lisp.command.stack import CommandsStack
from lisp.session import Session
from lisp.core.signal import Signal
from lisp.core.singleton import Singleton
from lisp.core.util import filter_live_properties
from lisp.cues.cue import Cue
from lisp.cues.cue_factory import CueFactory
from lisp.cues.cue_model import CueModel
from lisp.cues.media_cue import MediaCue
from lisp.ui.layoutselect import LayoutSelect
from lisp.ui.mainwindow import MainWindow
from lisp.ui.settings.app_configuration import AppConfigurationDialog
from lisp.ui.settings.app_pages.cue import CueAppSettings
from lisp.ui.settings.app_pages.general import AppGeneral
from lisp.ui.settings.app_pages.layouts import LayoutsSettings
from lisp.ui.settings.app_pages.plugins import PluginsSettings
from lisp.ui.settings.cue_pages.cue_appearance import Appearance
from lisp.ui.settings.cue_pages.cue_general import CueGeneralSettingsPage
from lisp.ui.settings.cue_pages.media_cue import MediaCueSettings
from lisp.ui.settings.cue_settings import CueSettingsRegistry
from lisp.ui.ui_utils import translate

logger = logging.getLogger(__name__)


class Application(metaclass=Singleton):
    def __init__(self, app_conf):
        self.session_created = Signal()
        self.session_before_finalize = Signal()

        self.__conf = app_conf
        self.__cue_model = CueModel()
        self.__session = None
        self.__commands_stack = CommandsStack()
        self.__main_window = MainWindow(self)

        # Register general settings widget
        AppConfigurationDialog.registerSettingsPage(
            "general", AppGeneral, self.__conf
        )
        AppConfigurationDialog.registerSettingsPage(
            "general.cue", CueAppSettings, self.__conf
        )
        AppConfigurationDialog.registerSettingsPage(
            "layouts", LayoutsSettings, self.__conf
        )
        AppConfigurationDialog.registerSettingsPage(
            "plugins", PluginsSettings, self.__conf
        )

        # Register common cue-settings widgets
        CueSettingsRegistry().add(CueGeneralSettingsPage, Cue)
        CueSettingsRegistry().add(MediaCueSettings, MediaCue)
        CueSettingsRegistry().add(Appearance)

        # Connect mainWindow actions
        self.__main_window.new_session.connect(self.__new_session_dialog)
        self.__main_window.save_session.connect(self.__save_to_file)
        self.__main_window.open_session.connect(self.__load_from_file)

    @property
    def conf(self):
        """:rtype: lisp.core.configuration.Configuration"""
        return self.__conf

    @property
    def session(self):
        """:rtype: lisp.core.session.Session"""
        return self.__session

    @property
    def window(self):
        """:rtype: lisp.ui.mainwindow.MainWindow"""
        return self.__main_window

    @property
    def layout(self):
        """:rtype: lisp.layout.cue_layout.CueLayout"""
        return self.__session.layout

    @property
    def cue_model(self):
        """:rtype: lisp.cues.cue_model.CueModel"""
        return self.__cue_model

    @property
    def commands_stack(self):
        """:rtype: lisp.command.stack.CommandsStack """
        return self.__commands_stack

    def start(self, session_file=""):
        # Show the mainWindow maximized
        self.__main_window.showMaximized()

        if exists(session_file):
            self.__load_from_file(session_file)
        else:
            layout_name = self.conf.get("layout.default", "nodefault")

            if layout_name.lower() != "nodefault":
                self.__new_session(layout.get_layout(layout_name))
            else:
                self.__new_session_dialog()

    def finalize(self):
        self.__delete_session()

        self.__cue_model = None
        self.__main_window = None

    def __new_session_dialog(self):
        """Show the layout-selection dialog"""
        try:
            # Prompt the user for a new layout
            dialog = LayoutSelect(self, parent=self.window)
            if dialog.exec() == QDialog.Accepted:
                # If a file is selected load it, otherwise load the layout
                if dialog.sessionPath:
                    self.__load_from_file(dialog.sessionPath)
                else:
                    self.__new_session(dialog.selected())
            else:
                if self.__session is None:
                    # If the user close the dialog, and no layout exists
                    # the application is closed
                    qApp.quit()
        except Exception:
            logger.critical(
                translate("ApplicationError", "Startup error"), exc_info=True
            )
            qApp.quit()

    def __new_session(self, layout):
        self.__delete_session()
        self.__session = Session(layout(application=self))

        self.session_created.emit(self.__session)

    def __delete_session(self):
        if self.__session is not None:
            self.session_before_finalize.emit(self.session)

            self.__commands_stack.clear()
            self.__session.finalize()
            self.__session = None

    def __save_to_file(self, session_file):
        """Save the current session into a file."""
        self.session.session_file = session_file

        # Get session settings
        session_props = self.session.properties()
        session_props.pop("session_file", None)

        # Get session cues
        session_cues = []
        for cue in self.layout.cues():
            session_cues.append(
                cue.properties(defaults=False, filter=filter_live_properties)
            )

        session_dict = {"session": session_props, "cues": session_cues}

        # Write to a file the json-encoded session
        with open(session_file, mode="w", encoding="utf-8") as file:
            if self.conf.get("session.minSave", False):
                file.write(json.dumps(session_dict, separators=(",", ":")))
            else:
                file.write(json.dumps(session_dict, sort_keys=True, indent=4))

        # Save last session path
        self.conf.set("session.lastPath", dirname(session_file))
        self.conf.write()

        # Set the session as saved
        self.commands_stack.set_saved()
        self.window.updateWindowTitle()

    def __load_from_file(self, session_file):
        """ Load a saved session from file """
        try:
            with open(session_file, mode="r", encoding="utf-8") as file:
                session_dict = json.load(file)

            # New session
            self.__new_session(
                layout.get_layout(session_dict["session"]["layout_type"])
            )
            self.session.update_properties(session_dict["session"])
            self.session.session_file = session_file

            # Load cues
            for cues_dict in session_dict.get("cues", {}):
                cue_type = cues_dict.pop("_type_", "Undefined")
                cue_id = cues_dict.pop("id")
                try:
                    cue = CueFactory.create_cue(cue_type, cue_id=cue_id)
                    cue.update_properties(cues_dict)
                    self.cue_model.add(cue)
                except Exception:
                    name = cues_dict.get("name", "No name")
                    logger.exception(
                        translate(
                            "ApplicationError",
                            'Unable to create the cue "{}"'.format(name),
                        )
                    )

            self.commands_stack.set_saved()
        except Exception:
            logger.exception(
                translate(
                    "ApplicationError",
                    'Error while reading the session file "{}"',
                ).format(session_file)
            )
            self.__new_session_dialog()
