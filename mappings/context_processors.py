from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from mappings.models import Mapping, PipelineGroup, PipelineGroupAssignment

def pipeline_groups_context(request):
    """Context processor exposing pipeline groups and counts globally for the left-hand navigation sidebar."""
    if not request.user.is_authenticated:
        return {}

    try:
        # 1. Fetch custom groups
        custom_groups = list(PipelineGroup.objects.all().order_by('name'))

        # 2. Fetch custom assignments
        assignments = PipelineGroupAssignment.objects.all().select_related('group')
        mapping_to_custom_group = {a.mapping_id: a.group for a in assignments}

        # 3. Retrieve all active mappings
        mappings = Mapping.objects.filter(is_active=True)

        # Apply creator filter if present
        selected_creator_name = request.GET.get('created_by_name', '').strip()
        if selected_creator_name:
            mappings = mappings.filter(
                Q(created_by__username__icontains=selected_creator_name) |
                Q(created_by__first_name__icontains=selected_creator_name) |
                Q(created_by__last_name__icontains=selected_creator_name)
            )
    except (OperationalError, ProgrammingError):
        # Database tables do not exist yet (migration not run)
        return {
            'sidebar_groups': [{'key': 'all', 'name': 'All Pipelines', 'count': 0, 'is_custom': False}],
            'sidebar_selected_group': 'all',
        }


    # 4. Define default convention naming prefixes
    DEFAULT_CONVENTIONS = [
        ('lh_to_mkt_uc', 'LH_to_MKT_UC'),
        ('mkt_ora_to_mkt_uc', 'MKT_ORA_TO_MKT_UC'),
        ('mkt_cloud_pg_to_mkt_uc', 'MKT_CLOUD_PG_TO_MKT_UC'),
        ('edw_to_lh', 'EDW_TO_LH'),
    ]

    # Initialize count dictionaries
    counts = {
        'all': len(mappings),
        'lh_to_mkt_uc': 0,
        'mkt_ora_to_mkt_uc': 0,
        'mkt_cloud_pg_to_mkt_uc': 0,
        'edw_to_lh': 0,
        'other': 0,
    }
    for cg in custom_groups:
        counts[f"custom_{cg.id}"] = 0

    # Calculate counts
    for m in mappings:
        custom_grp = mapping_to_custom_group.get(m.id)
        if custom_grp:
            key = f"custom_{custom_grp.id}"
            if key in counts:
                counts[key] += 1
            else:
                counts['other'] += 1
        else:
            name_lower = m.name.lower()
            assigned_default = False
            for prefix_lower, _ in DEFAULT_CONVENTIONS:
                if name_lower.startswith(prefix_lower):
                    counts[prefix_lower] += 1
                    assigned_default = True
                    break
            if not assigned_default:
                counts['other'] += 1

    # 5. Build list of groups for navigation submenu
    sidebar_groups = [
        {'key': 'all', 'name': 'All Pipelines', 'count': counts['all'], 'is_custom': False}
    ]
    for key, canonical in DEFAULT_CONVENTIONS:
        sidebar_groups.append({'key': key, 'name': canonical, 'count': counts[key], 'is_custom': False})
    for cg in custom_groups:
        assigned_pids = [mid for mid, grp in mapping_to_custom_group.items() if grp.id == cg.id]
        sidebar_groups.append({
            'key': f"custom_{cg.id}",
            'id': cg.id,
            'name': cg.name,
            'count': counts[f"custom_{cg.id}"],
            'is_custom': True,
            'pipelines_ids': assigned_pids
        })
    sidebar_groups.append({'key': 'other', 'name': 'Other Pipelines', 'count': counts['other'], 'is_custom': False})

    selected_group = request.GET.get('group', 'all').strip()
    selected_creator_name = request.GET.get('created_by_name', '').strip()

    return {
        'sidebar_groups': sidebar_groups,
        'sidebar_selected_group': selected_group,
        'sidebar_selected_creator_name': selected_creator_name,
    }
