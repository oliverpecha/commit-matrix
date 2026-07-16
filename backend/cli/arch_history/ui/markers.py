from backend.services.architecture.models import HistoryReport

class TimelineMarkers:
    def __init__(self, report: HistoryReport, **kwargs):
        commit_target = kwargs.get('commit_target')
        snapshot_prefix = kwargs.get('snapshot_prefix')
        smart_target = kwargs.get('smart_target')
        since = kwargs.get('since')
        until = kwargs.get('until')
        self.start = None
        self.end = None
        self.is_single = False

        def deep_find(v_str):
            if not v_str: return None
            v = str(v_str).strip().lower()
            if v.isdigit():
                return {'topo': int(v), 'type': 'commit'}
            
            for e in report.entries:
                if e.snapshot_sig and e.snapshot_sig.lower().startswith(v):
                    return {'topo': e.trigger.topo_id if e.trigger else 0, 'type': 'snapshot'}
                if e.trigger and e.trigger.commit_sig and e.trigger.commit_sig.lower().startswith(v):
                    return {'topo': e.trigger.topo_id, 'type': 'commit'}
                for c in (e.successive_used_by or []):
                    if c.commit_sig.lower().startswith(v):
                        return {'topo': c.topo_id, 'type': 'commit', 'parent_topo': e.trigger.topo_id if e.trigger else None}
                for run in (e.reappeared_runs or []):
                    for c in run:
                        if c.commit_sig.lower().startswith(v):
                            return {'topo': c.topo_id, 'type': 'commit', 'parent_topo': e.trigger.topo_id if e.trigger else None}
            return None

        val = smart_target or commit_target or snapshot_prefix
        # Bind the universal parameter back down so sub-label extractors fire seamlessly
        if smart_target and not commit_target and not snapshot_prefix:
            commit_target = smart_target
        if val:
            if "-" in str(val):
                p1, p2 = str(val).split("-", 1)
                self.start = deep_find(p1)
                self.end = deep_find(p2)
                if self.start and self.end and self.start['topo'] > self.end['topo']:
                    self.start, self.end = self.end, self.start
            else:
                self.start = deep_find(val)
                self.end = self.start
                self.is_single = True
        elif since or until:
            if since:
                for e in report.entries:
                    if e.trigger and e.trigger.date and e.trigger.date >= since:
                        self.start = {'topo': e.trigger.topo_id, 'type': 'commit'}
                        break
            if until:
                for e in reversed(list(report.entries)):
                    if e.trigger and e.trigger.date and e.trigger.date <= until:
                        self.end = {'topo': e.trigger.topo_id, 'type': 'commit'}
                        break

    def _get_label(self, match_dict, topo_id, check_type):
        if not match_dict or match_dict['topo'] != topo_id or match_dict['type'] != check_type:
            return None
        if self.is_single:
            return "          <- [Target]"
        if self.start and self.start['topo'] == topo_id and self.start['type'] == check_type:
            if self.end and self.end['topo'] == topo_id and self.end['type'] == check_type:
                return "          <- [Range Start & End]"
            return "          <- [Range Start]"
        if self.end and self.end['topo'] == topo_id and self.end['type'] == check_type:
            return "          <- [Range End]"
        return None

    def get_commit_marker(self, topo_id):
        return self._get_label(self.start, topo_id, 'commit') or self._get_label(self.end, topo_id, 'commit') or ""

    def get_snapshot_marker(self, topo_id):
        return self._get_label(self.start, topo_id, 'snapshot') or self._get_label(self.end, topo_id, 'snapshot') or ""

    def get_hidden_marker(self, hidden_entries):
        if not hidden_entries: return ""
        topos = [e.trigger.topo_id for e in hidden_entries if e.trigger]
        
        has_start = self.start and (self.start['topo'] in topos or self.start.get('parent_topo') in topos)
        has_end = self.end and (self.end['topo'] in topos or self.end.get('parent_topo') in topos)
        
        if has_start and has_end:
            if self.is_single: return "          <- [Target hidden by --compact]"
            return "          <- [Range Start & End hidden by --compact]"
        elif has_start:
            if self.is_single: return "          <- [Target hidden by --compact]"
            return "          <- [Range Start hidden by --compact]"
        elif has_end:
            return "          <- [Range End hidden by --compact]"
        return ""
