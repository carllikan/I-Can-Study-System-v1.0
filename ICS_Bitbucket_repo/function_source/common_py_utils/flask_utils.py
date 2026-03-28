def apply_security_headers(response):
    """Apply security headers to a Flask response object."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"


    #### if we have a list of domains want to be limited 
    #### Set the Access-Control-Allow-Origin header only if needed for CORS 
    #### like the following: prob need to be limited by Annex domain only
    #### cuz the backend api is designed to interact with frontend only
    # allowed_origins = ["https://example.com", "https://anotherdomain.com"]
    response.headers["Access-Control-Allow-Origin"]= "*"
    return response
