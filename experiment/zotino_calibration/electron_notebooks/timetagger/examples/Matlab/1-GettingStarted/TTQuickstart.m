%
% The TTQuickstart.m gives an overview of the API of the Time Tagger.
%
% create a timetagger instance
tagger = TimeTagger;

% simple counter on channels 1 and 2 with 1 ms binwidth (1e9 ps) and 1000 points for each channel
disp('****************************************');
disp('*** Demonstrate a counter time trace ***');
disp('****************************************');
disp(' ');
disp('Create counters on channels 1 and 2 with 1 ms binwidth and 1000 points.');
disp(' ');

count = TTCounter(tagger, [1 2], 1e9, 1000);

% apply the built-in test signal (~0.8 to 0.9 MHz) to channels
disp('Enabling test signal on channel 1.'); disp(' ');
tagger.setTestSignal(1, true);
pause(.5);
% turn on signal on channel 1 later
disp('Enabling test signal on channel 2.'); disp(' ');
tagger.setTestSignal(2, true);
% wait until the 1000 values should be filled
pause(.5);

%retrieve the data
data = count.getData();

figure(1)
% here is a pitfall: you have to cast count.getIndex() to a double first -
% otherwise it is a integer division which screws up your plot
plot(double(count.getIndex())/1e12, data);
xlabel('Time (s)');
ylabel('Counrate (kHz)');
legend('channel 1', 'channel 2', 'Location', 'East');
title('Time trace of the click rate on channel 1 and 2')
text(0.1,400, {'The built-in test signal (~ 800 to 900 kHz)', 'is applied first to channel 1', 'and 0.5 s later to channel 2.'})

%%

%cross correlation between channels 1 and 2
%binwidth=1000 ps, n_bins=3000, thus we sample 3000 ns
%we should see the correlation delta peaks at a bit more than 1000 ns distance
disp('*************************************');
disp('*** Demonstrate cross correlation ***');
disp('*************************************');
disp(' ');
disp('Create a cross correlation on channels 1 and 2 with 1 ns binwidth and 3000 points.');
disp(' ');

corr = TTCorrelation(tagger, 1, 2, 1000, 3000);
corr.startFor(1e12) % 1s
while corr.isRunning()
    pause(0.1)
end
figure(2)
plot(double(corr.getIndex())/1e3, corr.getData())
xlabel('Time (ns)')
ylabel('Clicks')
title('Cross correlation between channel 1 and 2')
text(-1400,300000, { ...
'The built-in test signal is applied', ...
'to channel 1 and channel 2.' ...
'The peak distance corresponds to' ...
'the period of the test signal.' });
text(100,300000, { ...
'Note: the decreasing peak heights', ...
'and broadening of the peaks', ...
'reflects the jitter of the built-in', ...
'test signal, which is much larger', ...
'than the instrument jitter.'});


%%

% cross correlation between channels 1 and 2
% binwidth=10 ps, n_bins=400, thus we sample 4 ns
% The standard deviation of the peak
% is the root mean square sum of the
% input jitters of channels 1 and 2
disp('Create a cross correlation on channels 1 and 2 with 10 ps binwidth and 400 points.'); disp(' ');
corr = TTCorrelation(tagger, 1, 2, 10, 400);
corr.startFor(2e12) %2s
while corr.isRunning()
    pause(0.1)
end
figure(3)
plot(corr.getIndex(), corr.getData())
title('High res cross correlation showing <60 ps jitter', 'FontWeight', 'normal')
xlabel('Time (ps)')
ylabel('Clicks')
text(-1500,8e4, { ...
'The half width of the peak is', ...
'sqrt(2) times the instrument jitter.', ...
'The shift of the peak from zero', ...
'is the propagation delay of the', ...
'built-in test signal.'});

%%

disp('**********************************************************');
disp('*** Demonstrate overflow handling with the data object ***');
disp('**********************************************************');

rising_edges = tagger.getChannelList(TTChannelEdge.Rising);
if strcmp(tagger.getModel(), 'Time Tagger Ultra')
    falling_edges = tagger.getChannelList(TTChannelEdge.Falling);
    channels = [rising_edges(1:4) falling_edges(1:4)];
else
    channels = rising_edges(1);
end

tagger.setTestSignal(channels, true);
counter = TTCounter(tagger, channels, 1000000000, 60000);
default_divider = tagger.getTestSignalDivider();
disp('The test signal divider will be reduced until overflows occur.')
fprintf('The default test signal divider is %d\n', default_divider)

pause(2)
divider = default_divider;

while divider > 1 && ~tagger.getOverflows()
    divider = idivide(divider, 2);
    fprintf("divider =  %d\n", divider)
    tagger.setTestSignalDivider(divider);
    pause(5)
end

fprintf('\nOverflows occurred at test signal divider of %d\n', divider)
% We let the Time Tagger run for five more seconds in the overflow
pause(5)
tagger.setTestSignalDivider(default_divider);
pause(3)
counter.stop();

data_object = counter.getDataObject();
mask = data_object.getOverflowMask();
indices = double(data_object.getIndex()) / 1e12;
data = data_object.getData();
data_with_overflow_mask = double(data(1, :)) / 1e3;
data_with_overflow_mask(logical(mask)) = nan;

figure(4);
plot(indices, data_with_overflow_mask);
text(1, max(data_with_overflow_mask, [], "all") / 1.2, [ ... ,
    "In the overflow mode", ...
    "there are gaps in the curve.", ...
    "After the overflown buffer is", ...
    "emptied by the USB transfer, it", ...
    "it can accumulate normal time-tags", ...
    "for a short period, before", ...
    "it overflows again. These time-tags", ...
    "are displayed between the gaps"]);
xlabel('Time (s)');
ylabel('kCounts');

%%
[~, maxIndex] = max(corr.getData());
index = corr.getIndex();
propagation_delay = abs(index(maxIndex));

disp('************************************');
disp('*** Demonstrate virtual channels ***');
disp('************************************');
disp(' ');
disp('Create a virtual channel that contains all tags of channel 1 and channel 2.');
disp(' ');
ch1_or_ch2 = TTCombiner(tagger, [1 2]);
disp(['The virtual channel was assigned the channel number ', num2str(ch1_or_ch2.getChannel()), '.']);
disp(' ');
disp(['Create a virtual channel that contains coincidence clicks of channel 1 and channel 2 within a +-', num2str(propagation_delay), ' ps window.']);
disp(' ');
ch1_and_ch2 = TTCoincidence(tagger, [1 2], propagation_delay);
disp(['The virtual channel was assigned the channel number ', num2str(ch1_or_ch2.getChannel()), '.']);
disp(' ');
disp('Create a countrate on channel 1 and the virtual channels.');
disp(' ');
countrate = TTCountrate(tagger, [1, ch1_or_ch2.getChannel(), ch1_and_ch2.getChannel]);
countrate.startFor(1e12) % 1s

while countrate.isRunning()
    pause(0.1)
end

data = countrate.getData();
disp('Count rates');
disp(['  channel 1:    ' num2str(round(data(1))) ' counts / s']);
disp(['  ch1 and ch2:  ' num2str(round(data(2))) ' counts / s']);
disp(['  coincidences: ' num2str(round(data(3))) ' counts / s']);
disp(' ');
disp('Here, we have used a coincidence window that coincides just with the propagation delay');
disp('between ch0 and ch1. Due to jitter, approximately half of the coincidence counts');
disp('fall outside of this coincidence range. Therefore, the coincidence countrate is');
disp('approximately half of the original count rate.');
disp(' ');



%% 
disp('**************************************************');
disp('*** Demonstrate virtual channels: Coincidences ***');
disp('**************************************************');

disp('Create virtual channels that contains the coincidences for the channel combination [1 2] and [1 2 3].');
coincidenceGroups = {};
coincidenceGroups{1} = [1 2];
coincidenceGroups{2} = [1 2 3];
coincidences = TTCoincidences(tagger, coincidenceGroups, propagation_delay);
coincidencesChannels = coincidences.getChannels();
disp(['The virtual channels were assigned to the channel number ', num2str(coincidencesChannels), '.']);
disp(' ');
disp('Create a countrate for the virtual channels.');
disp(' ');
countrate = TTCountrate( tagger, coincidencesChannels );
countrate.startFor(1e12) % 1s
while countrate.isRunning()
    pause(0.1)
end
data = countrate.getData();
disp('Count rates');
disp(['  coincidences ch 1 and 2:  ' num2str(round(data(1))) ' counts / s']);
disp(['  coincidences ch 1, 2 and 3:  ' num2str(round(data(2))) ' counts / s']);
disp(' ');
disp('The coincidences rate of ch 1 and 2 is the same as in the measurement before.');
disp('The count rate including channel 3 is zero because no test signal is running');
disp('on channel 3.');
disp(' ');

%%
disp(' ');
disp('*****************************');
disp('*** Demonstrate filtering ***');
disp('*****************************');
disp(' ');
disp('Enabling event filter.');
tagger.setConditionalFilter(1,4);
disp(' ');
disp('Enabling test signal on channel 1 and channel 4.');
disp(' ');
tagger.setTestSignal(1, true)
tagger.setTestSignal(4, true)
rate = TTCountrate(tagger, [1 4]);
rate.startFor(1e12) % 1s
while rate.isRunning()
    pause(0.1)
end
disp('Count rates');
data = rate.getData();
disp(['  channel 1: ' num2str(round(data(1))) ' counts / s']);
disp(['  channel 4: ' num2str(round(data(2))) ' counts / s']);
disp(' ');
disp('Disabling test signal on channel 1.');
disp(' ');
tagger.setTestSignal(1, false);
rate.clear()
rate.startFor(1e12) % 1s
while rate.isRunning()
    pause(0.1)
end
disp('Count rates');
data = rate.getData();
disp(['  channel 1: ' num2str(data(1)) ' counts / s']);
disp(['  channel 4: ' num2str(data(2)) ' counts / s']);
disp(' ');
disp('Here, we have used the event filter between channel 1 and channel 4');
disp('to suppress time tags on channel 4. The filter drops time tags on');
disp('channel 4 unless they were preceded by a tag on channel 1. First, since the tags are');
disp('simultaneous on both channels, but there is a finite jitter the count rate on channel 4');
disp('is reduced by some amount. Now, as we disable the test signal on channel 1, all time');
disp('tags on channel 4 are suppressed and a count rate of 0 is measured, even though the test');
disp('signal is active. The filtering is useful to tame signals with data rates > 8 MHz such as');
disp('synchronization signals from pulsed lasers in fluorescence lifetime measurements.');
disp(' ');
%%
disp('*****************************************');
disp('*** Demonstrate trigger level control ***');
disp('*****************************************');
disp(' ');
disp('Disable test signals and filter.');
disp(' ');
tagger.setTestSignal(1, false)
tagger.setTestSignal(2, false)
tagger.setTestSignal(4, false)
tagger.clearConditionalFilter()
% set the trigger levels on channel 1 and 2 to 0.5 V
% (this is the default value at startup)
disp('Set trigger levels on channel 1 and 2 to 0.5 volts.');
disp(' ');
tagger.setTriggerLevel(1, 0.5)
tagger.setTriggerLevel(2, 0.5)

%%
disp('**************************************');
disp('*** Access the raw time tag stream ***');
disp('**************************************');
disp(' ');
disp('Enable test signals.');
disp(' ');
tagger.setTestSignal(1, true)
tagger.setTestSignal(2, true)
stream = TTTimeTagStream(tagger, 1000000, [1 2]);
stream.startFor(0.5e12) % 0.5s
while stream.isRunning()
    pause(0.1)
end
data = stream.getData();
timestamps = data.getTimestamps();
channels = data.getChannels();
disp(['Total number of tags stored in the buffer: ' num2str(data.size)]);
disp('Show the first 10 tags');
for i = 1:min(data.size, 10)
    disp(['  time in ps: ' num2str(timestamps(i)) ' signal on channel: ' num2str(channels(i))]);
end
disp(' ');
clear stream

%%
disp('*********************');
disp('*** Scope example ***');
disp('*********************');
disp(' ');
scope = TTScope(tagger, 1, 2, 10000000, 1, 1000000);
scope.startFor(1e12) % 1s
while scope.isRunning()
    pause(0.1)
end
% getData() returns a nested array which in not available as a naitive type
% in Matlab. Therefore the Event[][] must be converted into something
% which can be plotted:
data = scope.getData();
dataCh0 = data(1);
if dataCh0(1).state == SwabianInstruments.TimeTagger.State.UNKNOWN
    warning('No data received on channel 0 for Scopte test');
else
    % to plot the data we have to convert each edge into two data points
    x = zeros(1,dataCh0.Length*2);
    y = zeros(1,dataCh0.Length*2);
    for i=1:dataCh0.Length
        x(i*2) = dataCh0(i).time;
        y(i*2) = dataCh0(i).state == SwabianInstruments.TimeTagger.State.HIGH;
        x(i*2-1) = dataCh0(i).time;
        y(i*2-1) = dataCh0(i).state == SwabianInstruments.TimeTagger.State.LOW;
    end
    figure(5)
    plot(x/1000000,y)
    ylabel('ch 1')
    xlabel('time (us)');
end
disp(' ');

%%
disp('************************');
disp('*** startFor example ***');
disp('************************');
disp(' ');
disp('With the startFor method, the measurement time can be set with a parameter.');
disp('StartFor clears the current data (optional parameter) and stops the measurement after');
disp('the time passed as a parameter (here 3s).');
corr = TTCorrelation(tagger, 1, 2, 10, 400);
corr.startFor(3e12, true) % 3s
while (corr.isRunning)
    pause(0.4)
    disp(['Current acquisition time: ' num2str(double(corr.getCaptureDuration)/1e12) ' s']);
end
figure(6)
plot(double(corr.getIndex())/1e3, corr.getData())
xlabel('Time (ns)')
ylabel('Clicks')
title('Cross correlation acquired for 3 seconds.')
disp(' ');

%%
% Remove a measurement
% Even when a measurement is stopped, e.g., via .stop(), data for the channels which in principle can be used by the measurement 
% will be transferred via USB from the Time Tagger to the Computer consuming USB bandwidth.
% To remove a measurement, clear all references to this measurement or remove the measurement explicitly by calling .delete()
% e.g.
clear count

%%
% disconnect the Time Tagger
clear tagger


disp('*****************************');
disp('*** Matlab GUI **************');
disp('*****************************');
disp(' ');
disp('A Draft for a Matlab GUI can be found');
disp('within the `2-GuiDraft` folder.')


%%
disp('*****************************');
disp('*** Dump and Load example ***');
disp('*****************************');
disp(' ');
disp('An example of how to Dump and Load the raw time tags can be found');
disp('within the `3-DumpAndLoad` folder.')
