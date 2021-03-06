# This file is part of the Frescobaldi project, http://www.frescobaldi.org/
#
# Copyright (c) 2008 - 2014 by Wilbert Berendsen
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
Export to Music XML.

Using ly.music document tree to convert the source to XML.

Uses functions similar to items.Document.iter_music() to iter through
the node tree. But information about where a node branch ends
is also added.

This approach substitues the previous method of using ly.lex directly
to parse the source. It should prove more stable and easier to implement.

"""

from __future__ import unicode_literals

import documentinfo
import ly.music

from . import create_musicxml
from . import ly2xml_mediator

#excluded from parsing
excl_list = ['Version', 'Midi', 'Layout', 'Scheme', 'SchemeItem', 'PathItem']


class End():
    """ Extra class that gives information about the end of Container
    elements in the node list. """
    def __init__(self, node):
        self.node = node


class ParseSource():
    """ creates the XML-file from the source code according to the Music XML standard """

    def __init__(self):
        self.musxml = create_musicxml.CreateMusicXML()
        self.mediator = ly2xml_mediator.Mediator()
        self.relative = False
        self.tuplet = False
        self.scale = ''
        self.grace_seq = False
        self.trem_rep = 0
        self.piano_staff = 0
        self.numericTime = False
        self.voice_sep = False
        self.sims_and_seqs = []

    def parse_tree(self, doc):
        mustree = documentinfo.music(doc)
        # print(mustree.dump())
        header_nodes = self.iter_header(mustree)
        if header_nodes:
            self.parse_nodes(header_nodes)
        score = self.get_score(mustree)
        if score:
            mus_nodes = self.iter_score(score, mustree)
        else:
            mus_nodes = self.find_score_sub(mustree)
        self.mediator.new_section("fallback") #fallback/default section
        self.parse_nodes(mus_nodes)

    def parse_nodes(self, nodes):
        """Work through all nodes by calling the function with the
        same name as the nodes class."""
        if nodes:
            for m in nodes:
                func_name = m.__class__.__name__ #get instance name
                # print func_name
                if func_name not in excl_list:
                    try:
                        func_call = getattr(self, func_name)
                        func_call(m)
                    except AttributeError as ae:
                        print "Warning: "+func_name+" not implemented!"
                        print(ae)
                        pass
        else:
            print("Warning! Couldn't parse source!")

    def musicxml(self, prettyprint=True):
        self.mediator.check_score()
        self.iterate_mediator()
        xml = self.musxml.musicxml(prettyprint)
        return xml

    ##
    # The different source types from ly.music are here sent to translation.
    ##

    def Assignment(self, assignm):
        """Because assignments in score are substituted, this should only be
        header assignments."""
        if isinstance(assignm.value(), ly.music.items.Markup):
            pass
        elif isinstance(assignm.value(), ly.music.items.String):
            self.mediator.new_header_assignment(assignm.name(), assignm.value().value())

    def MusicList(self, musicList):
        if musicList.token == '<<':
            if self.look_ahead(musicList, ly.music.items.VoiceSeparator):
                self.mediator.new_snippet('sim-snip')
                self.voice_sep = True
            else:
                self.sims_and_seqs.append('sim')
        elif musicList.token == '{':
            if self.sims_and_seqs and self.sims_and_seqs[-1] == 'sim':
                self.mediator.new_section('simultan')
            self.sims_and_seqs.append('seq')
            # print(self.sims_and_seqs)

    def Chord(self, chord):
        self.mediator.clear_chord()

    def Q(self, q):
        self.mediator.copy_prev_chord(q.duration, self.relative)

    def Context(self, context):
        """ \context """
        self.in_context = True
        if context.context() in ['PianoStaff', 'GrandStaff']:
            self.mediator.new_part(piano=True)
            self.piano_staff = 1
        elif context.context() == 'Staff':
            if self.piano_staff:
                if self.piano_staff > 1:
                    self.mediator.set_voicenr(nr=self.piano_staff+3)
                self.mediator.new_section('piano-staff'+str(self.piano_staff))
                self.mediator.set_staffnr(self.piano_staff)
                self.piano_staff += 1
            else:
                self.mediator.new_part()
            self.mediator.add_staff_id(context.context_id())
        elif context.context() == 'Voice':
            self.sims_and_seqs.append('voice')
            if context.context_id():
                self.mediator.new_section(context.context_id())
            else:
                self.mediator.new_section('voice')

    def VoiceSeparator(self, voice_sep):
        self.mediator.new_snippet('sim')
        self.mediator.set_voicenr(add=True)

    def Change(self, change):
        """ A \\change music expression. Changes the staff number. """
        if change.context() == 'Staff':
            self.mediator.set_staffnr(0, staff_id=change.context_id())

    def PipeSymbol(self, barcheck):
        """ PipeSymbol = | """
        self.mediator.new_bar()

    def Clef(self, clef):
        """ Clef \clef"""
        self.mediator.new_clef(clef.specifier())

    def KeySignature(self, key):
        self.mediator.new_key(key.pitch().output(), key.mode())

    def Relative(self, relative):
        pass

    def Note(self, note):
        """ notename, e.g. c, cis, a bes ... """
        #print(note.token)
        if note.length():
            self.mediator.new_note(note, self.relative)
            if self.tuplet:
                self.mediator.change_to_tuplet(self.fraction, self.ttype)
                self.ttype = ""
            if self.grace_seq:
                self.mediator.new_grace()
            if self.trem_rep:
                self.mediator.set_tremolo(trem_type='start', repeats=self.trem_rep)
        else:
            if isinstance(note.parent(), ly.music.items.Relative):
                self.mediator.set_relative(note)
                self.relative = True
            elif isinstance(note.parent(), ly.music.items.Chord):
                self.mediator.new_chord(note, note.parent().duration, self.relative)
                # chord as grace note
                if self.grace_seq:
                    self.mediator.new_chord_grace()

    def Tempo(self, tempo):
        """ Tempo direction, e g '4 = 80' """
        self.mediator.new_tempo(tempo.duration.tokens, tempo.tempo(), tempo.text())

    def Tie(self, tie):
        """ tie ~ """
        self.mediator.tie_to_next()

    def Rest(self, rest):
        """ rest, r or R. Note: NOT by command, i.e. \rest """
        if rest.token == 'R':
            self.scale = 'R'
        self.mediator.new_rest(rest)

    def Skip(self, skip):
        """ invisible rest/spacer rest (s or command \skip)"""
        if 'lyrics' in self.sims_and_seqs:
            self.mediator.new_lyrics_item(skip.token)
        else:
            self.mediator.new_rest(skip)

    def Scaler(self, scaler):
        """
        \times \tuplet \scaleDurations

        This will not work yet for `\scaleDurations`,
        because the fraction is not set in attribute `scaling`.

        """
        if scaler.token == '\\scaleDurations':
            self.ttype = ""
        else:
            self.ttype = "start"
        self.tuplet = True
        self.fraction = scaler.scaling

    def Number(self, number):
        pass

    def Articulation(self, art):
        """An articulation, fingering, string number, or other symbol."""
        self.mediator.new_articulation(art.token)

    def Postfix(self, postfix):
        pass

    def Beam(self, beam):
        pass

    def Slur(self, slur):
        """ Slur, '(' = start, ')' = stop. """
        if slur.token == '(':
            self.mediator.set_slur("start")
        elif slur.token == ')':
            self.mediator.set_slur("stop")

    def Dynamic(self, dynamic):
        """Any dynamic symbol."""
        self.mediator.new_dynamics(dynamic.token[1:])

    def Grace(self, grace):
        self.grace_seq = True

    def TimeSignature(self, timeSign):
        self.mediator.new_time(timeSign.numerator(), timeSign.fraction(), self.numericTime)

    def Repeat(self, repeat):
        if repeat.specifier() == 'volta':
            self.mediator.new_repeat('forward')
        elif repeat.specifier() == 'unfold':
            self.mediator.new_snippet('unfold')
        elif repeat.specifier() == 'tremolo':
            self.trem_rep = repeat.repeat_count()

    def Tremolo(self, tremolo):
        self.mediator.set_tremolo(duration=int(tremolo.duration.token))

    def With(self, cont_with):
        print(cont_with.tokens)

    def Set(self, cont_set):
        if cont_set.property() == 'instrumentName':
            self.mediator.set_partname(cont_set.value().value())
        elif cont_set.property() == 'midiInstrument':
            self.mediator.set_partmidi(cont_set.value().value())
        elif cont_set.property() == 'stanza':
            self.mediator.new_lyric_nr(cont_set.value().value())
        else:
            print(cont_set.property())

    def Command(self, command):
        """ \bar, \rest etc """
        if command.token == '\\rest':
            self.mediator.note2rest()
        elif command.token == '\\numericTimeSignature':
            self.numericTime = True
        elif command.token == '\\defaultTimeSignature':
            self.numericTime = False
        elif command.token.find('voice') == 1:
            self.mediator.set_voicenr(command.token[1:], piano=self.piano_staff)
        else:
            print(command.token)

    def String(self, string):
        prev = self.get_previous_node(string)
        if prev and prev.token == '\\bar':
            self.mediator.create_barline(string.value())

    def LyricsTo(self, lyrics_to):
        """A \\lyricsto expression. """
        self.mediator.new_lyric_section('lyricsto'+lyrics_to.context_id(), lyrics_to.context_id())
        self.sims_and_seqs.append('lyrics')

    def LyricText(self, lyrics_text):
        """A lyric text (word, markup or string), with a Duration."""
        self.mediator.new_lyrics_text(lyrics_text.token)

    def LyricItem(self, lyrics_item):
        """Another lyric item (skip, extender, hyphen or tie)."""
        self.mediator.new_lyrics_item(lyrics_item.token)

    def LyricMode(self, lyric_mode):
        """A \\lyricmode, \\lyrics or \\addlyrics expression."""
        pass

    def End(self, end):
        if isinstance(end.node, ly.music.items.Scaler):
            if end.node.token == '\scaleDurations':
                self.mediator.change_to_tuplet(self.fraction, "")
            else:
                self.mediator.change_to_tuplet(self.fraction, "stop")
            self.tuplet = False
            self.fraction = None
        elif isinstance(end.node, ly.music.items.Grace): #Grace
            self.grace_seq = False
        elif end.node.token == '\\repeat':
            if end.node.specifier() == 'volta':
                self.mediator.new_repeat('backward')
            elif end.node.specifier() == 'unfold':
                for n in range(end.node.repeat_count()):
                    self.mediator.add_snippet('unfold')
            elif end.node.specifier() == 'tremolo':
                if self.look_ahead(end.node, ly.music.items.MusicList):
                    self.mediator.set_tremolo(trem_type="stop", repeats=self.trem_rep)
                else:
                    self.mediator.set_tremolo(trem_type="single", repeats=self.trem_rep)
                self.trem_rep = 0
        elif isinstance(end.node, ly.music.items.Context):
            self.in_context = False
            if end.node.context() == 'Voice':
                self.mediator.check_voices()
                self.sims_and_seqs.pop()
            elif end.node.context() == 'Staff':
                if not self.piano_staff:
                    self.mediator.check_part()
            elif end.node.context() in ['PianoStaff', 'GrandStaff']:
                self.mediator.check_voices()
                self.mediator.check_part()
                self.piano_staff = 0
                self.mediator.set_voicenr(nr=1)
        elif end.node.token == '<<':
            if self.voice_sep:
                self.mediator.check_voices_by_nr()
                self.mediator.revert_voicenr()
                self.voice_sep = False
            elif not self.piano_staff:
                self.mediator.check_voices()
                self.mediator.check_part()
                self.sims_and_seqs.pop()
        elif end.node.token == '{':
            if self.sims_and_seqs:
                self.sims_and_seqs.pop()
        elif end.node.token == '\\lyricsto':
            self.mediator.check_lyrics(end.node.context_id())
            self.sims_and_seqs.pop()
        else:
            # print("end:"+end.node.token)
            pass

    ##
    # Additional node manipulation
    ##

    def get_previous_node(self, node):
        """ Returns the nodes previous node
        or false if the node is first in its branch. """
        parent = node.parent()
        i = parent.index(node)
        if i > 0:
            return parent[i-1]
        else:
            return False

    def simple_node_gen(self, node):
        """Unlike iter_score are the subnodes yielded without substitution."""
        for n in node:
            yield n
            for s in self.simple_node_gen(n):
                yield s

    def iter_header(self, tree):
        """Iter only over header nodes."""
        for t in tree:
            if isinstance(t, ly.music.items.Header):
                return self.simple_node_gen(t)

    def get_score(self, node):
        """ Returns (first) Score node or false if no Score is found. """
        for n in node:
            if isinstance(n, ly.music.items.Score) or isinstance(n, ly.music.items.Book):
                return n
        return False

    def iter_score(self, scorenode, doc):
        """Iter over score. Similar to items.Document.iter_music."""
        for s in scorenode:
            n = doc.substitute_for_node(s) or s
            yield n
            for n in self.iter_score(n, doc):
                yield n
        if isinstance(scorenode, ly.music.items.Container):
            yield End(scorenode)

    def find_score_sub(self, doc):
        """Find substitute for scorenode. Takes first music node that isn't
        an assignment."""
        for n in doc:
            if not isinstance(n, ly.music.items.Assignment):
                if isinstance(n, ly.music.items.Music):
                    return self.iter_score(n, doc)

    def look_ahead(self, node, find_node):
        """Looks ahead in a container node and returns True
        if the search is successful."""
        for n in node:
            if isinstance(n, find_node):
                return True
        return False

    ##
    # The xml-file is built from the mediator objects
    ##

    def iterate_mediator(self):
        """ The mediator lists are looped through and outputed to the xml-file. """
        # self.mediator.score.debug_score(['tuplet'])
        if self.mediator.score.title:
            self.musxml.create_title(self.mediator.score.title)
        for ctag in self.mediator.score.creators:
            self.musxml.add_creator(ctag, self.mediator.score.creators[ctag])
        for itag in self.mediator.score.info:
            self.musxml.create_score_info(itag, self.mediator.score.info[itag])
        if self.mediator.score.rights:
            self.musxml.add_rights(self.mediator.score.rights)
        for part in self.mediator.score.partlist:
            if part.barlist:
                self.musxml.create_part(part.name, part.midi)
                self.mediator.set_first_bar(part)
            else:
                print "Warning: empty part: "+part.name
            for bar in part.barlist:
                self.musxml.create_measure()
                for obj in bar.obj_list:
                    if isinstance(obj, ly2xml_mediator.BarAttr):
                        if obj.has_attr():
                            self.musxml.new_bar_attr(obj.clef, obj.time, obj.key, obj.mode, obj.divs)
                        if obj.repeat:
                            self.musxml.add_barline(obj.barline, obj.repeat)
                        elif obj.barline:
                            self.musxml.add_barline(obj.barline)
                        if obj.staves:
                            self.musxml.add_staves(obj.staves)
                        if obj.multiclef:
                            for mc in obj.multiclef:
                                self.musxml.add_clef(sign=mc[0][0], line=mc[0][1], nr=mc[1], oct_ch=mc[0][2])
                        if obj.tempo:
                            self.musxml.create_tempo(obj.tempo.metr, obj.tempo.midi, obj.tempo.dots)
                    elif isinstance(obj, ly2xml_mediator.BarMus):
                        if obj.dynamic['before']:
                            if obj.dynamic['before']['mark']:
                                self.musxml.add_dynamic_mark(obj.dynamic['before']['mark'])
                            if obj.dynamic['before']['wedge']:
                                self.musxml.add_dynamic_wedge(obj.dynamic['before']['wedge'])
                        if isinstance(obj, ly2xml_mediator.BarNote):
                            self.musxml.new_note(obj.grace, [obj.base_note, obj.alter, obj.pitch.octave, obj.note.accidental_token],
                            obj.base_scaling, obj.voice, obj.type, self.mediator.divisions, obj.dot, obj.chord)
                            if obj.tie:
                                self.musxml.tie_note(obj.tie)
                            if obj.slur:
                                self.musxml.add_slur(1, obj.slur) #LilyPond doesn't allow nested slurs so the number can be 1
                            if obj.artic:
                                self.musxml.new_articulation(obj.artic)
                            if obj.ornament:
                                self.musxml.new_simple_ornament(obj.ornament)
                            if obj.tremolo[1]:
                                self.musxml.add_tremolo(obj.tremolo[0], obj.tremolo[1])
                            if obj.fingering:
                                self.musxml.add_fingering(obj.fingering)
                            if obj.lyric:
                                for l in obj.lyric:
                                    try:
                                       self.musxml.add_lyric(l[0], l[1], l[2], l[3])
                                    except IndexError:
                                        self.musxml.add_lyric(l[0], l[1], l[2])
                        elif isinstance(obj, ly2xml_mediator.BarRest):
                            if obj.skip:
                                self.musxml.new_skip(obj.base_scaling, self.mediator.divisions)
                            else:
                                self.musxml.new_rest(obj.base_scaling, obj.type, self.mediator.divisions, obj.pos,
                                obj.dot, obj.voice)
                        if obj.tuplet:
                            self.musxml.tuplet_note(obj.tuplet, obj.base_scaling, obj.ttype, self.mediator.divisions)
                        if obj.staff and not obj.skip:
                            self.musxml.add_staff(obj.staff)
                        if obj.dynamic['after']:
                            if obj.dynamic['after']['mark']:
                                self.musxml.add_dynamic_mark(obj.dynamic['after']['mark'])
                            if obj.dynamic['after']['wedge']:
                                self.musxml.add_dynamic_wedge(obj.dynamic['after']['wedge'])
                        if obj.other_notation:
                            self.musxml.add_named_notation(obj.other_notation)
                    elif isinstance(obj, ly2xml_mediator.BarBackup):
                        self.musxml.new_backup(obj.base_scaling, self.mediator.divisions)


