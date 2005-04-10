#!/usr/bin/env python

import os
import os.path
import time
import string
import urllib
import sys
import cgi
import Image   ### Python Imaging Library
import ezt     ### Greg Stein's EZ Templating library

__version__ = '1.0'

###
###  URL SCHEME:
###
###     CGIURL[/PATH_INFO][?OPTIONS]
###
###  If PATH_INFO is a directory, shows a directory listing (subdirs
###  at the top, images at the bottom).  If a FILE, shows a thumbnail
###  of the file.
###
###  OPTIONS:
###
###     t=[on|off]   Thumbnail display on/off toggle
###     s=SIZE       Image maximum size
###

__version__ = '2.0'


THUMBNAIL_SIZE = 160
IMAGE_EXTENSIONS = ['.jpg', '.gif', '.png']

# Stylesheet info:
css_data = """
body { background: white; }
img { border: 10px;
      width: 160px;
      height: 120px; }
h1 { font-family: verdana, arial, helvetica, sans-serif;
     font-size: 24px;
     font-weight: bold;
     font-style: normal; }
h2 { font-family: verdana, arial, helvetica, sans-serif;
     font-size: 18px;
     font-weight: bold;
     font-style: italic; }
p { font-family: verdana, arial, helvetica, sans-serif;
    font-size: 11px;
    font-weight: normal;
    font-style: normal; }
#directory { margin-left: 0.25in;
             margin-right: 0.25in; }
#thumbnails { padding: 20px 0; }
.itemup { background: url('/icons/small/back.gif') no-repeat;
          font-family: times new roman, times, serif;
          font-size: 16px;
          font-style: italic;
          padding-left: 20px;
          margin-top: 0;
          margin-bottom: 0; }
.itemdir { background: url('/icons/small/dir.gif') no-repeat;
           font-family: times new roman, times, serif;
           font-size: 16px;
           padding-left: 20px;
           margin-top: 0;
           margin-bottom: 0; }
.itemfile { background: url('/icons/small/image2.gif') no-repeat;
            font-family: times new roman, times, serif;
            font-size: 16px;
            padding-left: 20px;
            margin-top: 0;
            margin-bottom: 0; }
"""

# -------------------------------------------------------------------------
# Do some setup-ish stuff.
# -------------------------------------------------------------------------

# Get environment info.
remote_addr = os.environ.get('REMOTE_ADDR')
script_name = os.environ.get('SCRIPT_NAME')
server_name = os.environ.get('SERVER_NAME')

# Build the script hrefs (one for running the script, one for
# appending photo path stuffs.
script_href = 'http://' + server_name + urllib.quote(script_name)
script_dir_href = os.path.dirname(script_href)

# Parse the path info.
path_info = os.environ.get('PATH_INFO')
if path_info and (path_info[0] == '/'):
    path_info = path_info[1:]
if path_info == '':
    path_info = None

# Get the current timestamp.
local_time = time.ctime()

# Check out CGI options.
cgi_vars = cgi.parse()
if cgi_vars.has_key('t'):
    thumbnails = (cgi_vars['t'])[0]
else:
    thumbnails = 'on'
    
# Initialize our subdirs and image list.
subdirs = []
images = []

# Loop over the directory entries at the path location.
location = path_info or '.'

# -------------------------------------------------------------------------
# Handle files -- an easy out.
# -------------------------------------------------------------------------

if os.path.isfile(location):
    base, ext = os.path.splitext(location)
    if ext.lower() in IMAGE_EXTENSIONS:
        try:
            import mimetypes
            im = Image.open(open(location, 'rb'))
            im.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            mimetype = mimetypes.guess_type(location)[0]
            print "Content-type: %s\n" % (mimetype)
            im.save(sys.stdout, im.format)
        except OSError:
            print "Content-type: text/plain\n\nUnknown file format!\n"
    sys.exit(0)
    
# -------------------------------------------------------------------------
# Handle directories -- the rest of the script.
# -------------------------------------------------------------------------

entries = os.listdir(location)
entries.sort()
for entry in entries:
    if os.path.isdir(os.path.join(location, entry)):
        subdirs.append(entry)
    else:
        base, ext = os.path.splitext(entry)
        if ext.lower() in IMAGE_EXTENSIONS:
            images.append(entry)

# -------------------------------------------------------------------------
# Print the header.
# -------------------------------------------------------------------------

print 'Content-type: text/html'
print ''
print '<html>'
print '<head>'
if path_info:
    print '<title>Photo Index: ' + location + '</title>'
else:
    print '<title>Photo Index</title>'
print '<style type="text/css">'
print css_data
print '</style>'
print '</head>'
print '<body>'
if path_info:
    print '<h1>Photo Index: ' + location + '</h1>'
else:
    print '<h1>Photo Index</h1>'
print '<p>'
print '<b>WARNING:</b> Pages with photos might take a while to load.<br/>'
print 'Folks with a slow Internet connection should probably'
print 'toggle the thumbnail display (located at the bottom of this'
print 'page) to <b>off</b>.'
print '</p>'

# -------------------------------------------------------------------------
# Print the directory listing section.
# -------------------------------------------------------------------------

print '<hr/>'
print '<div id="directory">'
subdirs.reverse()
base_href = script_href
if path_info:
    base_href = base_href + '/' + urllib.quote(path_info)
    this_href = os.path.dirname(base_href)
    if thumbnails == 'off':
        this_href = this_href + '?t=off'
    print '<p class="itemup"><a href="%s">[PARENT DIRECTORY]</a></p>' \
          % (this_href)
for subdir in subdirs:
    this_href = base_href + '/' + urllib.quote(subdir)        
    if thumbnails == 'off':
        this_href = this_href + '?t=off'
    print '<p class="itemdir"><a href="%s">%s</a></p>' % (this_href, subdir)
if thumbnails == 'off':
    for image in images:
        this_href = script_dir_href + '/' + \
                    urllib.quote(location + '/' + image)
        print '<p class="itemfile"><a href="%s">%s</a></p>' \
              % (this_href, image)
print '</div>'

# -------------------------------------------------------------------------
# If we are displaying thumbnails, display them.
# -------------------------------------------------------------------------

if thumbnails != 'off' and len(images):
    print '<div id="thumbnails">'
    for image in images:
        this_href = script_dir_href + '/' + \
                        urllib.quote(location + '/' + image)
        thumb_href = script_href + '/' + urllib.quote(location + '/' + image)
        print '<a href="%s"><img src="%s"/></a></li>' \
              % (this_href, thumb_href)
    print '</div>'

# -------------------------------------------------------------------------
# Print the options section.
# -------------------------------------------------------------------------

print '<h2>Options:</h2>'
print '<p>'
thumbnail_toggle_url = script_href
if path_info:
    thumbnail_toggle_url = thumbnail_toggle_url + '/' + urllib.quote(path_info)
if thumbnails != 'off':
    thumbnail_toggle_url = thumbnail_toggle_url + '?t=off'
print 'Thumbnail display is: <b>%s</b> [<a href="%s">toggle</a>]<br/>' \
      % (thumbnails, thumbnail_toggle_url)
print '</p>'

# -------------------------------------------------------------------------
# Print the footer.
# -------------------------------------------------------------------------

print '<hr/>'
print '<p><i>Photo indexing script by '
print '   <a href="http://www.red-bean.com/cmpilato/">C. Michael Pilato</a><br/>'
print '   <i>Current time: %s</i></p>' % (local_time)
print '</body>'
print '</html>'
