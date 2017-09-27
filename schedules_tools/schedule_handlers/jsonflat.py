from schedules_tools.schedule_handlers import jsonstruct


class ScheduleHandler_jsonflat(jsonstruct.ScheduleHandler_json):
    provide_export = True
    
    def export_schedule(self, out_file):
        return super(ScheduleHandler_jsonflat, self).export_schedule(
            out_file, flat=True)
