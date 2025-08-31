classdef TimeTagDumpReader
    % This class reads the binary file created with the Time Tagger "Dump"
    % measurement and provides simplified interface data access.

    properties (Access = private)
        mmap;
        data;
    end
    
    methods
        function obj = TimeTagDumpReader(filename)
            
            % Create the file to the memory mapping object
            obj.mmap = memmapfile(filename, 'Format', 'int8');
            % This changes the array shape without actual data reading.
            obj.data = reshape(obj.mmap.Data, 16, []); 
            % Actual disk access and data read will occur only when 
            % the obj.data property is accessed via this class methods.
        end
        
        function overflows = getOverflows(obj)
            %Returns logic array of overflow states for every timestamp.
            % DEPRECATED SINCE: 2.4.5.
            %   Use TimeTagDumpReader.getOverflowTypes() instead.
            warning('off', 'backtrace');
            warning("getOverflows() is deprecated. Instead use getOverflowTypes()");
            warning('on', 'backtrace');
            overflows = logical(obj.getOverflowTypes());
        end
        
        function ovfl_types = getOverflowTypes(obj)
            % Returns information about overflow occurrence and type.
            % Possible overflow type values:
            %   TimeTag = 0        No overflow occurred
            %   Error = 1          Hardware overflow
            %   OverflowBegin = 2  The first tag when overflow started
            %   OverflowEnd = 3    The last tag when overflow finished
            %   MissedEvents = 4   The tag contains information about
            %                      number of missed tags. To read the
            %                      missed events use getMissedEventsCount() 
            %                 
            ovfl_types = typecast(obj.data(1, :), 'uint8');
        end
        
        function counts = getMissedEvents(obj)
            % Returns an array of missed event counts.
            counts = typecast(reshape(obj.data(3:4, :), [],1), 'uint16');
        end
        
        function channels = getChannels(obj)
            % Returns an array of channel numbers for every timestamp.
            channels = typecast(reshape(obj.data(5:8, :), [],1), 'int32');
        end
        
        function timestamps = getTimestamps(obj)
            % Returns an array of timestamps.
            timestamps = typecast(reshape(obj.data(9:16, :), [],1), 'int64');
        end
        
        function TF = hasOverflows(obj)
            % Returns True if overflow was detected in any of the tags received.
            TF = any(obj.getOverflowTypes > 0);
        end
    end
end
