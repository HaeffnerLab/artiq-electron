%
% The MaximumTransferRate.m test the maximum transfer rate you can achieve
%

clear all;

% create a timetagger instance
tagger = TimeTagger;

disp('*******************************');
disp('*** Turn on the test signal ***');
disp('*******************************');

disp('The data transfer rate will be measured by turning on the internal test signal')
disp('on several channels, with which in total the USB transfer rate is exceeded.')
disp('By measuring the rate of incoming time tags, the maximum data rate is measured.')

disp('')
disp('Please close all other programs to get the maximum data rate possible.')
disp('')

allRisingChannels = tagger.getChannelList(TTChannelEdge.Rising); %get all channel numbers of the rising edges
if strcmp(tagger.getModel(), 'Time Tagger Ultra')
    % Time Tagger Ultra
    % set test signal rate: 25 MHz
    tagger.setTestSignalDivider(2);
    testChannels = allRisingChannels(1:4); % select the first 4 channels
    tagger.setTestSignal(testChannels, true);
    disp('Total rate: 4x 25 MHz');
else
    % Time Tagger 20
    % set test signal rate:
    % test signal rate ~2.5 MHz
    tagger.setTestSignalDivider(25);
    testChannels = allRisingChannels(1:4); % select the first 4 channels
    disp('Total rate: 4x 2.5 MHz');
end
tagger.setTestSignal(testChannels, true)

disp(' ');
disp('******************************************************');
disp('*** Capture the stream via the TimeTagStream class ***');
disp('******************************************************');
disp(' ');
disp('The TimeTagStream class stores the incoming tags in memory');
disp('and is therefore the fastest way to access the time tag stream.');
disp(' ');
bufferSize = 75e6; % tags
capture_time = 0.5; %s
averages = 20;
disp(['Capture buffer size: ' num2str(bufferSize/1e6)   ' MTags']);
disp(['Capture duration:    ' num2str(capture_time) ' s']);
disp(['Test runs:           ' num2str(averages)]);
disp(' ');

totalCounts = 0;
totalTime = 0;

transfer_rate = zeros(1, averages);
stream = TTTimeTagStream(tagger, bufferSize, testChannels);
tagger.sync();
tic;
startTime = toc;
endTime = startTime;
for i = 1:averages
    pause(capture_time - (toc - endTime));
    endTime = toc;
    data = stream.getData();
    dt = endTime - startTime;
    startTime = endTime;
    totalCounts = totalCounts + data.size;
    totalTime = totalTime + dt;
    transfer_rate(i) = double(data.size) / 1e6 / dt;
    fprintf('#%3d: %5.1f MTags/s | dt: %7.3f ms | buffer fill: %3.0f %%\n', i, transfer_rate(i), dt * 1e3, data.size * 100 / bufferSize);
end

transfer_rate = sort(transfer_rate);

fprintf('\n>>>  Average transfer rate: %4.1f MTags/s  <<<\n', double(totalCounts) / 1e6 / totalTime);

if strcmp(tagger.getModel(), 'Time Tagger Ultra')
    disp('The maximum transfer rate is not limited by USB 3.0 but by the single thread CPU performance.');
    disp('A very good processor (i9-9900K, max. 5 GHz) can process in total 70 MTags/s.');
    disp('If case the transfer rate dropping during the measurement compared the very first measurement points,');
    disp('your CPU is probably throttling. This happens especially with mobile processors.');
    disp('In case your data rate is only between 10-12 MTags/s, you have likely connected the Time Tagger')
    disp('to a USB 2.0 port, instead of a USB 3.0 port.');
else
    disp('The transfer rate should exceed 8 MTags/s and is limited by the USB 2.0 bandwidth.');
    disp('Usually, the CPU performance is not playing a role at these data rates.');
end

clear stream;
clear tagger