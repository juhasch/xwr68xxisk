import os
import sys
sys.path.insert(0, os.path.abspath('../..'))

project = 'XWR68XX ISK Radar Tools'
copyright = '2024, Juergen Hasch'
author = 'Juergen Hasch'
release = '1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

# Theme options
html_theme_options = {
    'style_external_links': True,
    'style_nav_header_background': '#2980B9',
    'navigation_depth': 4,
    'collapse_navigation': True,
    'sticky_navigation': True,
}

# These paths are either relative to html_static_path or fully qualified paths (eg. https://...)
html_css_files = [
    'custom.css',
]

# Configure source parsers
source_suffix = {
    '.md': 'markdown',
}

# Configure MyST-Parser
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "tasklist",
    "attrs_inline",
]

# Enable auto-generated header anchors
myst_heading_anchors = 2

# Root document
root_doc = 'index' 