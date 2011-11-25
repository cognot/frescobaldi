# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008 - 2011 by Wilbert Berendsen
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
# See http://www.gnu.org/licenses/ for more information.

"""
Documentation preferences.
"""

from __future__ import unicode_literals

from PyQt4.QtCore import QSettings, Qt
from PyQt4.QtGui import QComboBox, QCompleter, QGridLayout, QLabel, QVBoxLayout

import app
import icons
import preferences
import widgets.listedit
import widgets.dialog
import helpbrowser
import language_names


class Documentation(preferences.GroupsPage):
    def __init__(self, dialog):
        super(Documentation, self).__init__(dialog)

        layout = QVBoxLayout()
        self.setLayout(layout)
        
        layout.addWidget(Paths(self))
        layout.addWidget(Browser(self))
        layout.addStretch(1)


class Paths(preferences.Group):
    def __init__(self, page):
        super(Paths, self).__init__(page)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.paths = LilyDocPathsList()
        self.paths.changed.connect(self.changed)
        layout.addWidget(self.paths)
        
        app.translateUI(self)
    
    def translateUI(self):
        self.setTitle(_("Paths to LilyPond Documentation"))
        self.paths.setToolTip(_(
            "Add paths or URLs. See \"What's This\" for more information."))
        self.paths.setWhatsThis(_(
            "<p>Here you can add local paths or URLs pointing to LilyPond "
            "documentation. A local path should point to the directory where "
            "either the \"{documentation}\" directory lives, or the whole "
            "\"share/doc/lilypond/html/offline-root\" path.</p>\n"
            "<p>If those can't be found, documentation is looked for in all "
            "subdirectories of the given path, one level deep. This makes it "
            "possible to put multiple versions of LilyPond documentation in "
            "different subdirectories and have Frescobaldi automatically find "
            "them.</p>").format(documentation="Documentation"))
    
    def loadSettings(self):
        self.paths.setValue(QSettings().value("documentation/paths", []) or [])
        
    def saveSettings(self):
        s = QSettings()
        s.beginGroup("documentation")
        paths = self.paths.value()
        if paths:
            s.setValue("paths", paths)
        else:
            s.remove("paths")


class Browser(preferences.Group):
    def __init__(self, page):
        super(Browser, self).__init__(page)
        
        layout = QGridLayout()
        self.setLayout(layout)
        
        self.languagesLabel = QLabel()
        self.languages = QComboBox(currentIndexChanged=self.changed)
        layout.addWidget(self.languagesLabel, 0, 0)
        layout.addWidget(self.languages, 0, 1)
        
        items = ['']
        items.extend(language_names.languageName(l, l) for l in helpbrowser.translations)
        self.languages.addItems(items)
        
        app.translateUI(self)
    
    def translateUI(self):
        self.setTitle(_("Help Browser"))
        self.languagesLabel.setText(_("Preferred Language:"))
        self.languages.setItemText(0, _("English (untranslated)"))

    def loadSettings(self):
        lang = QSettings().value("documentation/language", "C")
        if lang not in helpbrowser.translations:
            i = 0
        else:
            i = helpbrowser.translations.index(lang) + 1
        self.languages.setCurrentIndex(i)
    
    def saveSettings(self):
        langs = ['C'] + helpbrowser.translations
        QSettings().setValue("documentation/language",
            langs[self.languages.currentIndex()])


class LilyDocPathsList(widgets.listedit.ListEdit):
    def openEditor(self, item):
        
        dlg = widgets.dialog.Dialog(self,
            _("Please enter a local path or a URL:"),
            app.caption("LilyPond Documentation"),
            icon = icons.get('lilypond-run'))
        urlreq = widgets.urlrequester.UrlRequester()
        urlreq.lineEdit.setCompleter(QCompleter([
            "http://lilypond.org/doc/v2.12/",
            "http://lilypond.org/doc/stable/",
            "http://lilypond.org/doc/latest/",
            ], urlreq.lineEdit))
        dlg.setMainWidget(urlreq)
        urlreq.setMinimumWidth(320)
        urlreq.lineEdit.setFocus()
        if dlg.exec_():
            item.setText(urlreq.path())
            return True
        return False

