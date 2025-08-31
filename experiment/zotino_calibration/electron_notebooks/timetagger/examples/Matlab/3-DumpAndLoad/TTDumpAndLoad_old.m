%
% The TTDumpAndLoad.m shows how to save and load the raw time tag stream
% 
% WARNING: The Dump measurement is deprecated. Please use FileWriter and
%          FileReader instead. This example is provided to show how to read 
%          existing files stored with Dump measurement.
%
%
clear all
% create a timetagger instance
disp('*****************************************************');
disp('*** Show save and load of the raw time tag stream ***');
disp('***  DUMP IS DEPRECATED, USE FileWriter INSTEAD   ***');
disp('*****************************************************');
tagger = TimeTagger;
tagger.reset();
channels = [1 2];
% apply a test signal to the selected channels
disp(' ');
disp('Enable the internal test signal.');
tagger.setTestSignal(channels, true);

%%
% create the file dump
disp(' ');
disp('Create a TTDump object which saves the raw time tags of the given channels.');
disp('Parameters:')
disp(' (1) Time Tagger object the dump belongs to:')
disp(' (2) file name for the raw time tag stream')
disp(' (3) maximum number of time tags to be dumped')
disp('     max file size: tags * 16 byte')
disp(' (4) OPTIONAL channels which are dumped')
disp('     For the case parameter (4) is skipped, he TTDump object will save all active channels.')
disp('     Active channels are channels which are used by another measurement class.');
disp('     The data throughput is higher for the configuration without parameter (4).');
disp(' ');
filename = fullfile(tempdir, 'example.dump');
disp(['Dump file name: ' filename]);
dump = TTDump(tagger, filename, 1e6, channels);
pause(1)
disp(' ');
disp('dump.stop() forces the filesystem to flush the file and stop the dump.');
dump.stop()
dump.delete();
clear dump
clear tagger

%%
% read back the dumped data
disp(' ');
disp('Read back the dumped stream from the filesystem using TimeTagDumpReader.');
disp(' .getOverflows()  (boolean) - flags which show that the internal buffer was exceeded and a time tags were discarded at that position');
disp(' .getChannels()   (integer) - channel number of the time tag');
disp(' .getTimestamps() (integer) - time stamp in ps (t=0 ps is where the Time Tagger was initialized or reset)');

dump_reader = TimeTagDumpReader(filename);


%%
%now the data can be accessed via methods of the dump_reader object

disp('Read all tags data from the file.');
channel = dump_reader.getChannels();
time = dump_reader.getTimestamps();
overflow_types = dump_reader.getOverflowTypes(); % TimeTag = 0, Error = 1, OverflowBegin = 2, OverflowEnd = 3, MissedEvents = 4
missed_events = dump_reader.getMissedEvents();
disp('Showing data from a few tags')
for i = 1:3
    fprintf('TAG# %8d \t t = %d ps \t channel: %d \t overflow_type: %d \t missed_events: %d \n', ...
        i, time(i), channel(i), overflow_types(i), missed_events(i));
end
disp(' ...');
fprintf('TAG# %8d \t t = %d ps \t channel: %d \t overflow_type: %d \t missed_events: %d \n\n', ...
        numel(time), time(end), channel(end), overflow_types(end), missed_events(end));

fprintf('Recoding duration: %d ps\n\n', time(end)-time(1));

disp('For some functions, the 64 bit integer timestamp must be converted to doubles for further processing in Matlab.');
disp('Please note that this may result in data loss as the "double" has smaller resolution than "int64"!');
mtime = double(time);

data_rate = 1e12 * numel(mtime)/(mtime(end)-mtime(1));
fprintf('\nAverage data rate: %0.1f counts/s (%0.2f Mbit/s)\n', data_rate, data_rate*8*16/1024/1024);

disp(' ');
disp('The raw time tag stream can be also accessed in real-time using the TimeTagStream class.');
disp('The TimeTagStream class returns the tags received directly from the hardware for on-the-fly processing.');
disp('See 1-GettingStarted/TTQuickstart.m for an example.');


disp('===============================')
disp('Deleting the temporary file.')
clear dump_reader;
delete(filename)