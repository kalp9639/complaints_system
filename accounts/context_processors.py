def base_context(request):
    return {
        'is_official': hasattr(request.user, 'official_profile')
    }
