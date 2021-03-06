"""
This module defines a detector for new data paths.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.
This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

import time
import os

from aminer import AMinerConfig
from aminer.AnalysisChild import AnalysisContext
from aminer.events import EventSourceInterface
from aminer.input import AtomHandlerInterface
from aminer.util import TimeTriggeredComponentInterface
from aminer.util import PersistenceUtil
from aminer.analysis import CONFIG_KEY_LOG_LINE_PREFIX


class NewMatchPathDetector(AtomHandlerInterface, TimeTriggeredComponentInterface, EventSourceInterface):
    """This class creates events when new data path was found in a parsed atom."""

    def __init__(self, aminer_config, anomaly_event_handlers, persistence_id='Default', auto_include_flag=False, output_log_line=True):
        """Initialize the detector. This will also trigger reading or creation of persistence storage location."""
        self.anomaly_event_handlers = anomaly_event_handlers
        self.auto_include_flag = auto_include_flag
        self.next_persist_time = None
        self.output_log_line = output_log_line
        self.aminer_config = aminer_config
        self.persistence_id = persistence_id

        PersistenceUtil.add_persistable_component(self)
        self.persistence_file_name = AMinerConfig.build_persistence_file_name(aminer_config, self.__class__.__name__, persistence_id)
        persistence_data = PersistenceUtil.load_json(self.persistence_file_name)
        if persistence_data is None:
            self.known_path_set = set()
        else:
            self.known_path_set = set(persistence_data)

    def receive_atom(self, log_atom):
        """
        Receive on parsed atom and the information about the parser match.
        @param log_atom the parsed log atom
        @return True if this handler was really able to handle and process the match. Depending on this information, the caller
        may decide if it makes sense passing the parsed atom also to other handlers.
        """
        unknown_path_list = []
        for path in log_atom.parser_match.get_match_dictionary().keys():
            if path not in self.known_path_set:
                unknown_path_list.append(path)
                if self.auto_include_flag:
                    self.known_path_set.add(path)
        if unknown_path_list:
            if self.next_persist_time is None:
                self.next_persist_time = time.time() + 600
            original_log_line_prefix = self.aminer_config.config_properties.get(CONFIG_KEY_LOG_LINE_PREFIX)
            if original_log_line_prefix is None:
                original_log_line_prefix = ''
            if self.output_log_line:
                sorted_log_lines = [log_atom.parser_match.match_element.annotate_match('') + os.linesep + repr(
                    unknown_path_list) + os.linesep + original_log_line_prefix + repr(log_atom.raw_data)]
            else:
                sorted_log_lines = [repr(unknown_path_list) + os.linesep + original_log_line_prefix + repr(log_atom.raw_data)]
            analysis_component = {'AffectedLogAtomPaths': list(unknown_path_list)}
            if self.output_log_line:
                match_paths_values = {}
                for match_path, match_element in log_atom.parser_match.get_match_dictionary().items():
                    match_value = match_element.match_object
                    if isinstance(match_value, bytes):
                        match_value = match_value.decode()
                    match_paths_values[match_path] = match_value
                analysis_component['ParsedLogAtom'] = match_paths_values
            event_data = {'AnalysisComponent': analysis_component}
            for listener in self.anomaly_event_handlers:
                listener.receive_event('Analysis.%s' % self.__class__.__name__, 'New path(es) detected', sorted_log_lines, event_data,
                                       log_atom, self)
        return True

    def get_time_trigger_class(self):
        """Get the trigger class this component can be registered for. This detector only needs persisteny triggers in real time."""
        return AnalysisContext.TIME_TRIGGER_CLASS_REALTIME

    def do_timer(self, trigger_time):
        """Check current ruleset should be persisted."""
        if self.next_persist_time is None:
            return 600

        delta = self.next_persist_time - trigger_time
        if delta < 0:
            self.do_persist()
            delta = 600
        return delta

    def do_persist(self):
        """Immediately write persistence data to storage."""
        PersistenceUtil.store_json(self.persistence_file_name, list(self.known_path_set))
        self.next_persist_time = None

    def allowlist_event(self, event_type, sorted_log_lines, event_data, allowlisting_data):
        """
        Allowlist an event generated by this source using the information emitted when generating the event.
        @return a message with information about allowlisting
        @throws Exception when allowlisting of this special event using given allowlisting_data was not possible.
        """
        if event_type != 'Analysis.%s' % self.__class__.__name__:
            raise Exception('Event not from this source')
        if allowlisting_data is not None:
            raise Exception('Allowlisting data not understood by this detector')
        allowlisted_str = ''
        for path_name in event_data[1]:
            if path_name in self.known_path_set:
                continue
            self.known_path_set.add(path_name)
            if allowlisted_str:
                allowlisted_str += ', '
            allowlisted_str += path_name
        return 'Allowlisted path(es) %s in %s' % (allowlisted_str, sorted_log_lines[0])
