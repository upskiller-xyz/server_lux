"""Swagger/Flasgger configuration for API documentation"""

import os
from src.__version__ import version


def get_swagger_template() -> dict:
    """Get Swagger template with API info and reusable definitions

    Returns:
        Dictionary containing Swagger template configuration
    """
    auth_type = os.getenv('AUTH_TYPE', 'token').lower()

    # Build security definitions based on auth type
    security_definitions = {}
    security_requirements = []

    if auth_type == 'token':
        security_definitions['Bearer'] = {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Token-based authentication. Enter your token in the format: Bearer <your_token>'
        }
        security_requirements.append({'Bearer': []})
    elif auth_type == 'auth0':
        security_definitions['Auth0'] = {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'Auth0 JWT authentication. Enter your JWT token in the format: Bearer <your_jwt_token>'
        }
        security_requirements.append({'Auth0': []})

    auth_info = ''
    if auth_type == 'token':
        auth_info = '\n\n**Authentication:** This API uses Bearer token authentication. Include your token in the Authorization header.'
    elif auth_type == 'auth0':
        auth_info = '\n\n**Authentication:** This API uses Auth0 JWT authentication. Include your JWT token in the Authorization header.'

    template = {
        'info': {
            'title': 'Server Lux API',
            'version': version,
            'description': f'''API documentation for Server Lux services{auth_info}

**Note:** When testing endpoints in Swagger UI, use valid example data:
- Mesh must contain complete triangles (vertices in multiples of 3)
- Each vertex must have [x, y, z] coordinates
- See individual endpoint examples for valid request formats
- For working examples, refer to example/demo.ipynb in the repository
'''
        },
        'definitions': {
            'Mesh': {
                'type': 'array',
                'description': '3D mesh as array of triangle vertex coordinates [[x,y,z], ...]. Must have vertices in multiples of 3 (each triangle has 3 vertices). The mesh should represent buildings/obstacles near the window position for realistic obstruction calculations.',
                'example': [
                    [-10, 0, 0], [10, 0, 0], [-10, 10, 0],
                    [10, 0, 0], [10, 10, 0], [-10, 10, 0],
                    [-5, 17, 0], [0, 17, 0], [-5, 17, 10],
                    [0, 17, 0], [0, 17, 10], [-5, 17, 10],
                    [-5, 8, 0], [0, 8, 0], [-5, 8, 10],
                    [0, 8, 0], [0, 8, 10], [-5, 8, 10]
                ],
                'items': {
                    'type': 'array',
                    'minItems': 3,
                    'maxItems': 3,
                    'items': {
                        'type': 'number'
                    }
                }
            },
            'CoordinateX': {
                'type': 'number',
                'description': 'X coordinate of window reference point',
                'example': 39.98
            },
            'CoordinateY': {
                'type': 'number',
                'description': 'Y coordinate of window reference point',
                'example': 48.78
            },
            'CoordinateZ': {
                'type': 'number',
                'description': 'Z coordinate of window reference point',
                'example': 18.65
            },
            'DirectionAngle': {
                'type': 'number',
                'description': 'Direction angle in degrees',
                'example': 45.0
            },
            'StartAngle': {
                'type': 'number',
                'description': 'Starting angle in degrees (default 17.5)',
                'example': 17.5
            },
            'EndAngle': {
                'type': 'number',
                'description': 'Ending angle in degrees (default 162.5)',
                'example': 162.5
            },
            'NumDirections': {
                'type': 'integer',
                'description': 'Number of directions to calculate (default 64)',
                'example': 64
            },
            'RoomPolygon': {
                'type': 'array',
                'description': 'Room boundary as 2D polygon coordinates',
                'example': [[0, 0], [0, 7], [-3, 7], [-3, 0]],
                'items': {
                    'type': 'array',
                    'items': {
                        'type': 'number'
                    }
                }
            },
            'WindowConfig': {
                'type': 'object',
                'description': 'Window configuration with 3D coordinates',
                'properties': {
                    'x1': {'type': 'number', 'description': 'X coordinate of first corner'},
                    'y1': {'type': 'number', 'description': 'Y coordinate of first corner'},
                    'z1': {'type': 'number', 'description': 'Z coordinate of first corner'},
                    'x2': {'type': 'number', 'description': 'X coordinate of second corner'},
                    'y2': {'type': 'number', 'description': 'Y coordinate of second corner'},
                    'z2': {'type': 'number', 'description': 'Z coordinate of second corner'},
                    'window_frame_ratio': {'type': 'number', 'description': 'Ratio of window frame to total area', 'example': 0.41}
                }
            },
            'ReferencePoint': {
                'type': 'object',
                'properties': {
                    'x': {'type': 'number', 'description': 'X coordinate'},
                    'y': {'type': 'number', 'description': 'Y coordinate'},
                    'z': {'type': 'number', 'description': 'Z coordinate'}
                }
            },
            'SuccessResponse': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'success'
                    }
                }
            },
            'ErrorResponse': {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'error'
                    },
                    'error': {
                        'type': 'string',
                        'description': 'Error message'
                    },
                    'error_type': {
                        'type': 'string',
                        'description': 'Error type identifier'
                    }
                }
            }
        }
    }

    # Add security definitions if authentication is enabled
    if security_definitions:
        template['securityDefinitions'] = security_definitions
        template['security'] = security_requirements

    return template


def get_swagger_config() -> dict:
    """Get Swagger UI configuration

    Returns:
        Dictionary containing Swagger UI config
    """
    return {
        'headers': [],
        'specs': [
            {
                'endpoint': 'apispec',
                'route': '/apispec.json',
                'rule_filter': lambda rule: True,
                'model_filter': lambda tag: True,
            }
        ],
        'static_url_path': '/flasgger_static',
        'swagger_ui': True,
        'specs_route': '/docs/'
    }
