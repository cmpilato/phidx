#!/usr/bin/env python

import os
import os.path
import time
import string
import urllib
import sys
import cgi

__version__ = '0.2'

# Stylesheet info:
css_data = """
BODY {
    background: white;
}
IMG {
    border: 10px;
    width: 160px;
    height: 120px;
}
H1 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 24px;
    font-weight: bold;
    font-style: normal;
}
H2 {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 18px;
    font-weight: bold;
    font-style: italic;
}
P {
    font-family: verdana, arial, helvetica, sans-serif;
    font-size: 11px;
    font-weight: normal;
    font-style: normal;
}

"""

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
entries = os.listdir(location)
entries.sort()
for entry in entries:
    if os.path.isdir(os.path.join(location, entry)):
        subdirs.append(entry)
    else:
        base, ext = os.path.splitext(entry)
        ext = string.lower(ext)
        if (ext == '.jpg') or (ext == '.gif') or (ext == '.png'):
            images.append(entry)

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

# Print a section for subdirectories.
print '<h2>Subdirectories:</h2>'
print '<ul>'
subdirs.reverse()
base_href = script_href
if path_info:
    base_href = base_href + '/' + urllib.quote(path_info)
    this_href = os.path.dirname(base_href)
    if thumbnails == 'off':
        this_href = this_href + '?t=off'
    print '<li style="font-style: italic;"><a href="%s">' \
          '[PARENT DIRECTORY]</a></li>' % (this_href)
for subdir in subdirs:
    this_href = base_href + '/' + urllib.quote(subdir)        
    if thumbnails == 'off':
        this_href = this_href + '?t=off'
    print '<li><a href="%s">%s</a></li>' % (this_href, subdir)
print '</ul>'

# If there are any actual images, print a section for them.    
if len(images):
    print '<h2>Photos:</h2>'
    if thumbnails == 'off':
        print '<ul>'
        for image in images:
            url = script_dir_href + '/' + urllib.quote(location + '/' + image)
            print '<li><a href="%s">%s</a></li>' % (url, image)
        print '</ul>'
    else:
        print '<p>'
        for image in images:
            url = script_dir_href + '/' + urllib.quote(location + '/' + image)
            print '<a href="%s"><img src="%s"/></a></li>' % (url, url)
        print '</p>'

# Print the options section.
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
print '<hr/>'
print '<p><i>Photo indexing script by '
print '   <a href="http://www.red-bean.com/cmpilato/">C. Michael Pilato</a><br/>'
print '   <i>Current time: %s</i></p>' % (local_time)
print '</body>'
print '</html>'
