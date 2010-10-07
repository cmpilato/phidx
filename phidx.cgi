#!/usr/bin/env python

### ------------------------------------------------------------------------
### phidx.cgi:  CGI script for dynamically serving thumbnailed
###             collections of images.
### ------------------------------------------------------------------------
###
### Copyright:  2005-2010 C. Michael Pilato <cmpilato@red-bean.com>,
###             2007-2009 Karl Fogel <kfogel@red-bean.com>
### 
### Licensed under the Apache License, Version 2.0 (the "License");
### you may not use this file except in compliance with the License.
### You may obtain a copy of the License at
### 
###     http://www.apache.org/licenses/LICENSE-2.0
### 
### Unless required by applicable law or agreed to in writing, software
### distributed under the License is distributed on an "AS IS" BASIS,
### WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
### See the License for the specific language governing permissions and
### limitations under the License.
###
### ------------------------------------------------------------------------

import os
import os.path
import time
import urllib
import sys
import cgi
import string
import fnmatch
import tempfile
import zipfile
import ConfigParser
import ezt

__version__ = '1.0-dev (r%s)' % ('$Rev$'[6:-2] or '???')

###
###  URL SCHEME:
###
###     CGIURL[/ALBUM][/PATH_INFO][?OPTIONS]
###
###  If PATH_INFO is a directory, shows a directory listing (subdirs
###  at the top, images at the bottom).  If a FILE, shows a thumbnail
###  of the file.
###
###  OPTIONS:
###
###     t=[on|off]    Thumbnail display on/off toggle
###     s=SIZE        Image size (0 = original)
###     d=[on|off]    Direct image mode (no wrapping HTML) on/off toggle
###     r=[0|1|2|3]   Image rotation (number x 90 degrees counterclockwise)
###     a=[PASSWORD]  Archive generation with (possibly optional) password
###


############################################################################

# Global Variables
COOKIE_KEY = 'phidx_opts='
COOKIE_VARS = [ 't', 's' ]
IMAGE_EXTENSIONS = ['.jpg', '.gif', '.png']

class UnknownAlbumException(Exception):
    pass
class MissingAlbumException(Exception):
    pass
class EmptyArchiveException(Exception):
    pass
class InvalidPasswordException(Exception):
    pass

class OptionSet:
    def __init__(self, options):
        vars(self).update(options)
    
class Config:
    def __init__(self):
        cgi_dir = os.path.dirname(sys.argv[0])
        template_file = os.path.join(cgi_dir, 'phidx.ezt')
        conf_file = os.path.join(cgi_dir, 'phidx.conf') 

        self.parser = None
        self.albums = {}
        self.defaults = {
            'thumbnail_size' : 120,
            'allowed_generated_image_sizes': [160, 320, 640],
            'enable_cache' : 0,
            'template' : template_file,
            'location' : None,
            'ignores' : '.*, CVS',
            'obscure' : 1,
            'archives' : 'off',
            }

        # Parse the conf-file, if one exists.
        if not os.path.isfile(conf_file):
            return
        
        self.parser = parser = ConfigParser.ConfigParser()
        parser.read(conf_file)
        if parser.has_section('defaults'):
            self._parse_options_section('defaults', self.defaults)
        if parser.has_section('albums'):
            for key, value in parser.items('albums', raw=1):
                self.albums[key] = value

    def _parse_options_section(self, section, options):
        # Parse option values:  [ type, is_list, name ]
        for is_int, is_list, oname \
            in [[ 1, 0, 'thumbnail_size' ],
                [ 1, 1, 'allowed_generated_image_sizes' ],
                [ 1, 0, 'enable_cache' ],
                [ 1, 0, 'obscure' ],
                [ 0, 0, 'template' ],
                [ 0, 1, 'ignores' ],
                [ 0, 0, 'archives' ],
                ]:
            if self.parser.has_option(section, oname):
                value = self.parser.get(section, oname)
                try:
                    if is_list:
                        value = filter(None, map(lambda x: x.strip(),
                                                 value.split(',')))
                        if is_int:
                            value = map(lambda x: int(x), value)
                    elif is_int:
                        value = int(value)
                    options[oname] = value
                except:
                    pass

    def get_albums(self):
        return self.albums.keys()

    def get_default_options(self):
        return OptionSet(self.defaults.copy())
    
    def get_album_options(self, album):
        options = self.defaults.copy()

        # If there's no album supplied, that's a problem.
        if not album:
            raise MissingAlbumException("Unable to determine which album you "
                                        "wish to view.")

        # If we don't recognize the album (either because we have no
        # config file, or because the album isn't present in that
        # file), that, too, is a problem.
        try:
            options['location'] = self.albums[album]
        except KeyError:
            raise UnknownAlbumException("There is no album named '%s' available "
                                        "for viewing." % (album))

        # If the album has an options overrides section, merge it into
        # the defaults.
        if self.parser.has_section(album):
            self._parse_options_section(album, options)

        # Finally, return the options.
        return OptionSet(options)
        

def _cookie_parse(cookie):
    # Parse the cookie into name/value pairs.
    cookie_vars = {}
    if cookie:
        start = cookie.find(COOKIE_KEY)
        if start != -1:
            end = cookie[start:].find(';')
            start = start + len(COOKIE_KEY)
            if end == -1:
                cookie = cookie[start:]
            else:
                cookie = cookie[start:start+end]
            pieces = cookie.split(',')
            for piece in pieces:
                nameval = piece.split('=')
                if nameval[0] in COOKIE_VARS:
                    cookie_vars[nameval[0]] = len(nameval) > 1 and nameval[1] or ''
    return cookie_vars

def _cookie_string(cookie_vars):
    # Unparse the COOKIE_VARS dictionary into a cookie string.
    pieces = []
    for name in COOKIE_VARS:
        if cookie_vars.get(name):
            pieces.append(name + '=' + cookie_vars[name])
    outstring = ','.join(pieces) or ''
    if outstring:
        outstring = '%s%s; path=/; expires=31-Dec-2012 23:59:59 GMT' \
                    % (COOKIE_KEY, outstring)
    return outstring
    
def _cgi_parse():
    cgi_data = cgi.parse(keep_blank_values=1)
    cgi_vars = {}
    for name in cgi_data.keys():
        if cgi_data[name]:
            cgi_vars[name] = cgi_data[name][0]
        else:
            raise Exception, name
            cgi_vars[name] = None
    return cgi_vars

def _cgi_string(cgi_vars):
    pieces = []
    for name in cgi_vars.keys():
        pieces.append(name + '=' + cgi_vars[name])
    outstring = '&'.join(pieces)
    return outstring and '?' + outstring or outstring

class Request:
    def __init__(self):
        """Do some setup-ish stuff."""
        
        # Get environment info.
        remote_addr = os.environ.get('REMOTE_ADDR')
        script_name = os.environ.get('SCRIPT_NAME')
        server_name = os.environ.get('SERVER_NAME')
        cookie = os.environ.get('HTTP_COOKIE')

        # Build the script hrefs (one for running the script, one for
        # appending photo path stuffs.
        self.script_name = script_name
        self.script_href = 'http://' + server_name + urllib.quote(script_name)
        self.script_dir_href = os.path.dirname(self.script_href)
        
        # Parse the path info.
        path_info = os.environ.get('PATH_INFO')
        path_pieces = []
        if path_info:
            path_pieces = filter(None, path_info.split('/'))
        if '..' in path_pieces:
            raise Exception, "Invalid URL"
        self.album = None
        if len(path_pieces):
            self.album = path_pieces[0]

        # Get the configuration bits.
        do_listing = 0
        self.config = Config()
        try:
            self.options = self.config.get_album_options(self.album)
            del path_pieces[0]
        except MissingAlbumException:
            self.album = None
            self.options = self.config.get_default_options()
            do_listing = 1
        path_info = '/'.join(path_pieces)
        if path_info == '':
            path_info = None
        self.path_info = path_info
        self.real_path = self.options.location
        if self.path_info:
            self.real_path = os.path.join(self.real_path, path_info)
        
        # Get the current timestamp.
        self.local_time = time.ctime()

        # Handle the cookie.
        self.cookie_vars = _cookie_parse(cookie)
        if self.cookie_vars.has_key('s'):
            self.cookie_vars['s'] = str(self._sanitize_size(
                int(self.cookie_vars['s'])))
        
        # CGI options, fetch and validate.
        self.cgi_vars = _cgi_parse()
        if self.cgi_vars.has_key('s'):
            self.cgi_vars['s'] = str(self._sanitize_size(
                int(self.cgi_vars['s'])))

        # Merge cookie data into CGI data; CGI wins.
        if not self.cgi_vars.has_key('s') \
           and self.cookie_vars.get('s'):
            self.cgi_vars['s'] = self.cookie_vars['s']
        if not self.cgi_vars.has_key('t') \
           and self.cookie_vars.get('t'):
            self.cgi_vars['t'] = self.cookie_vars['t']

        # What kind of request is this?
        if do_listing:
            self.do_album_listing()
        elif os.path.isfile(self.real_path):
            self.do_file()
        else:
            if self.cgi_vars.has_key('a'):
                self.do_archive()
            else:
                self.do_directory()

    def _sanitize_size(self, size):
        allowed_sizes = self.options.allowed_generated_image_sizes \
                        + [ self.options.thumbnail_size ]
        if size != 0 and size not in allowed_sizes:
            return max(allowed_sizes)
        else:
            return size
        
    def _gen_url(self, path_info, cgi_vars):
        base_href = self.script_href
        if self.album:
            base_href = base_href + '/' + urllib.quote(self.album)
        if path_info:
            base_href = base_href + '/' + urllib.quote(path_info)
        return base_href + _cgi_string(cgi_vars)

    def _init_template_data(self, is_dir):
        data = {
            'version' : __version__,
            'thumbnail_size' : self.options.thumbnail_size,
            'album' : self.album,
            'path' : self.path_info,
            'mode' : is_dir and "dir" or "file",
            'localtime' : self.local_time,
            }
        return data

    def _generate_output(self, data, extra_headers=[]):
        template = ezt.Template(self.options.template, 1, ezt.FORMAT_RAW)
        sys.stdout.write("Content-type: text/html\n")
        for header in extra_headers:
            sys.stdout.write(header + "\n")
        sys.stdout.write("\n")
        template.generate(sys.stdout, data)
        sys.exit(0)

    def _album_password(self):
        """Return the password configured for the current album."""
        password_file = os.path.join(os.path.join(self.options.location,
                                                  ".phidx", "password"))
        try:
            return open(password_file, 'r').readline().rstrip('\r\n')
        except:
            raise Exception, \
                  "Unable to read password file for '%s' album" \
                  % (self.album)

    def _cached_thumbnail_path(self, size, rotate):
        """Return the path of the cached thumbnail for the current
        image with SIZE and rotation ROTATE, or None of no such
        thumbnail is permitted or desired."""
        if not self.options.enable_cache:
            return None
        if not size:
            return None
        return os.path.join(os.path.dirname(self.real_path),
                            ".phidx", "thumbnails", str(size), str(rotate),
                            os.path.basename(self.real_path))

    def do_file(self):
        """Handle file displays."""
        filename = os.path.basename(self.real_path)
        import mimetypes
        mimetype = mimetypes.guess_type(self.real_path)[0]
        base, ext = os.path.splitext(self.real_path)
        if ext.lower() not in IMAGE_EXTENSIONS or not mimetype:
            raise Exception, "Unsupported file format!"
        size = int(self.cgi_vars.get('s', '0'))
        rotate = int(self.cgi_vars.get('r', '0'))

        if self.cgi_vars.get('d', 'off') == 'on':
            # Direct mode -- we're serving a picture.
            try:
                import Image

                # If thumbnailing, try for cached thumbnail image first,
                # else generate it on the fly (and then save in cache).
                cache_path = self._cached_thumbnail_path(size, rotate)
                im = None
                if cache_path and os.path.exists(cache_path):
                    try:
                        im = Image.open(open(cache_path, 'rb'))
                        print "Content-type: %s\n" % (mimetype)
                        im.save(sys.stdout, im.format)
                        return
                    except:
                        pass

                # If we get here, we weren't able to pull from a
                # previously made cache.  We'll process the image
                # request, caching the results if possible, but
                # provide those results to the client regardless.
                im = Image.open(open(self.real_path, 'rb'))
                format = im.format
                if size:
                    im.thumbnail((size, size))
                # Do rotation only after thumbnailing, for efficiency.
                im = im.rotate(rotate * 90)

                # Try to initialize cache and save our thumbnail to it.
                # If anything goes wrong, we'll choose not to care.
                if cache_path:
                    try:
                        if not os.path.exists(os.path.dirname(cache_path)):
                            os.makedirs(os.path.dirname(cache_path))
                        im.save(open(cache_path, 'wb'), format)
                        im = Image.open(open(cache_path, 'rb'))
                    except Exception:
                        pass

                # Print our header and image results.
                print "Content-type: %s\n" % (mimetype)
                im.save(sys.stdout, format)
            except IOError:
                raise
            except OSError:
                raise Exception, "Unsupported file format!"
        else:
            # Indirect mode -- we're serving an HTML picture wrapper.
            if not size:
                raise Exception, "Script error -- no indirect mode " \
                      "support for unsized images."
            rotate_l = (rotate + 1) % 4
            rotate_r = (rotate - 1) % 4

            # Determine the previous and next images (if any).
            prev_href = next_href = None
            subdirs, images = self.get_dirents(os.path.dirname(self.real_path),
                                               os.path.dirname(self.path_info))
            num_images = len(images)
            for i in range(num_images):               
                if images[i].name == filename:
                    prev_href = images[(i + num_images - 1) % num_images].href
                    next_href = images[(i + 1) % num_images].href
                    ### TODO: Should we nullify any rotation values carried
                    ### in these hrefs?
                    break
                
            # Generate output
            data = self._init_template_data(0)
            data.update({
                'up_href' : self._gen_url(os.path.dirname(self.path_info), {}),
                'prev_href' : prev_href,
                'next_href' : next_href,
                'rotate_left_href' : self._gen_url(self.path_info,
                                                   {'s' : str(size),
                                                    'd' : 'off',
                                                    'r' : str(rotate_l)}),
                'rotate_right_href' : self._gen_url(self.path_info,
                                                    {'s' : str(size),
                                                     'd' : 'off',
                                                     'r' : str(rotate_r)}),
                'image_full_href' : self._gen_url(self.path_info,
                                                  {'s' : '0',
                                                   'd' : 'on',
                                                   'r' : str(rotate)}),
                'image_href' : self._gen_url(self.path_info,
                                             {'s' : str(size),
                                              'd' : 'on',
                                              'r' : str(rotate)}),
                })
            self._generate_output(data)

    def _get_settings(self):
        settings = []
        thumbnail_options = []
        thumbnail_options.append(_item(name='on', value='on'))
        thumbnail_options.append(_item(name='off', value='off'))
        settings.append(_item(description='Thumbnail display',
                              name='t',
                              value=self.cgi_vars.get('t', 'on') == 'on' \
                                  and 'on' or 'off',
                              options=thumbnail_options))
        size_options = []
        for size in self.options.allowed_generated_image_sizes:
            size_options.append(_item(name=str(size), value=str(size)))
        size_options.append(_item(name='original', value='0'))
        settings.append(_item(description='Preferred image size',
                              name='s',
                              value=int(self.cgi_vars.get('s', '0')),
                              options=size_options))
        return settings

    def get_dirents(self, directory, directory_path_info):
        """Return a 2-tuple containing _item()s for the subdirectories
        of DIRECTORY and _item()s for the viewable files in that
        directory.  DIRECTORY_PATH_INFO is the URL relative to the
        script location which refers to DIRECTORY."""

        subdirs = []
        images = []

        base_path = directory_path_info
        entries = os.listdir(directory)
        entries.sort()

        def _is_ignored(filename):
            for ignore in self.options.ignores:
                if fnmatch.fnmatch(filename, ignore):
                    return 1
            return 0
            
        for entry in entries:
            # Skip ignored stuff
            if _is_ignored(entry):
                continue
            real_path = os.path.join(directory, entry)
            if not os.access(real_path, os.R_OK):
                continue
            if os.path.isdir(real_path):
                # Subdirectory
                subdir = _item(name=entry,
                               href=self._gen_url(os.path.join(base_path,
                                                               entry),
                                                  self.cgi_vars))
                subdirs.append(subdir)
            else:
                # File
                base, ext = os.path.splitext(entry)
                if ext.lower() not in IMAGE_EXTENSIONS:
                    continue

                cgi_vars = self.cgi_vars.copy()
                cgi_vars['d'] = 'off'
                thumb_cgi_vars = self.cgi_vars.copy()
                thumb_cgi_vars['s'] = str(self.options.thumbnail_size)
                thumb_cgi_vars['d'] = 'on'
                if not int(self.cgi_vars.get('s', '0')):
                    cgi_vars['d'] = 'on'

                thumb_href = self._gen_url(os.path.join(base_path, entry),
                                           thumb_cgi_vars)
                img_href = self._gen_url(os.path.join(base_path, entry),
                                         cgi_vars)
                images.append(_item(name=entry,
                                    href=img_href,
                                    thumbnail_href=thumb_href))
        subdirs.reverse() ### TODO :  Custom sort
        return subdirs, images
    
    def do_directory(self):
        """Handle directory listings."""
        # -----------------------------------------------------------------
        # Setup the directory listing section, which includes subdirectories
        # and, if not displaying thumbnails, image files.
        # -----------------------------------------------------------------

        subdirs, images = self.get_dirents(self.real_path,
                                           self.path_info or '')
        up_href = None
        if self.path_info:
            up_href = self._gen_url(os.path.dirname(self.path_info),
                                    self.cgi_vars)

        # -----------------------------------------------------------------
        # Generate the output.
        # -----------------------------------------------------------------

        archive_form_href = archive_href = None
        if images:
            if self.options.archives == "private":
                archive_form_href = self._gen_url(self.path_info, {})
            elif self.options.archives == "on":
                archive_href = self._gen_url(self.path_info, {'a': ''})
            
        data = self._init_template_data(1)
        data.update({
            'settings' : self._get_settings(),
            'settings_form_href' : self._gen_url(self.path_info, {}),
            'up_href' : up_href,
            'subdirs' : subdirs,
            'images' : images,
            'thumbnails' : ezt.boolean(self.cgi_vars.get('t', 'on') == 'on'),
            'archive_form_href' : archive_form_href,
            'archive_href' : archive_href,
            })
        self._generate_output(data,
                              ['Set-cookie: %s'
                               % (_cookie_string(self.cgi_vars))])

    def do_archive(self):
        """Handle archive generation."""
        if self.options.archives == "private":
            if self.cgi_vars.get('a') != self._album_password():
                raise InvalidPasswordException("Archive password is missing or "
                                               "incorrect.")
        elif self.options.archives == "on":
            pass
        else:
            raise Exception, "Archive generation is disabled"

        entries = os.listdir(self.real_path)
        image_paths = []
        for entry in entries:
            full_path = os.path.join(self.real_path, entry)
            if not os.path.isfile(full_path):
                continue
            base, ext = os.path.splitext(entry)
            if ext.lower() not in IMAGE_EXTENSIONS:
                continue
            image_paths.append(full_path)

        if not image_paths:
            raise EmptyArchiveException("There are no images to download in "
                                        "the requested directory.")
        
        sys.stdout.write("Content-type: application/zip\n"
                         "Content-disposition: attachment; filename=%s.zip\n\n"
                         % (self.album))

        # Spew a ZIP stream at stdout.  Don't bother compressing it --
        # these are, after all, image files.
        #
        # NOTE: We can't just stream *directly* to sys.stdout, because
        # the zipfile library wants to tell() and seek() on it, which
        # can't be done.  So we use a temporary file.  *Sigh*.
        tmp_fp = tempfile.TemporaryFile()
        zip_fp = zipfile.ZipFile(tmp_fp, mode='w')
        try:
            for image_path in image_paths:
                zip_fp.write(image_path, os.path.basename(image_path))
        finally:
            zip_fp.close()
        tmp_fp.seek(0, os.SEEK_SET)
        while 1:
            chunk = tmp_fp.read(4096)
            if not chunk:
                break
            sys.stdout.write(chunk)
        tmp_fp.close()

    def do_album_listing(self):
        subdirs = []
        albums = self.config.get_albums()
        albums.sort()
        cgi_vars = self.cgi_vars.copy()
        if cgi_vars.has_key('a'):
          del(cgi_vars['a'])
        for album in albums:
            options = self.config.get_album_options(album)
            if options.obscure != 0:
                continue
            subdir = _item(name=album,
                           href=self._gen_url(album, cgi_vars))
            subdirs.append(subdir)

        if not subdirs:
            raise MissingAlbumException("Unable to determine which album you "
                                        "wish to view.")
        
        data = self._init_template_data(1)
        data.update({
            'settings' : self._get_settings(),
            'settings_form_href' : self._gen_url(self.path_info, {}),
            'up_href' : None,
            'subdirs' : subdirs,
            'images' : [],
            'thumbnails' : ezt.boolean(cgi_vars.get('t', 'on') == 'on'),
            'archive_form_href' : None,
            'archive_href' : None,
            })
        self._generate_output(data,
                              ['Set-cookie: %s'
                               % (_cookie_string(cgi_vars))])
        

class _item:
  def __init__(self, **kw):
    vars(self).update(kw)


def test(path_info, query_string):
    os.environ['SCRIPT_NAME'] = '/SCRIPT_NAME'
    os.environ['SERVER_NAME'] = 'SERVER_NAME'
    os.environ['PATH_INFO'] = path_info
    os.environ['QUERY_STRING'] = query_string
    req = Request()


def print_exception(detailed=False):
    exc_type, exc, exc_tb = sys.exc_info()
    try:
        import traceback
        tb = string.join(traceback.format_exception(exc_type, exc, exc_tb), '')
    finally:
        # Prevent circular reference. sys.exc_info documentation warns
        # "Assigning the traceback return value to a local variable in
        # a function that is handling an exception will cause a
        # circular reference..."  This is all based on 'exc_tb', and
        # we're now done with it. Toss it.
        del exc_tb
    print 'Content-type: text/html\n'
    print '<h1>phidx: An Error Occured</h1>'
    if detailed:
        print '<p><strong>Traceback:</strong></p>'
        print '<pre style="color: red">%s</pre>' % (tb)
        print '<p><strong>Environment:</strong></p>'
        print '<ul>'
        print '<li>HTTP_COOKIE: %s</li>' % (os.environ.get('HTTP_COOKIE'))
        print '<li>PATH_INFO: %s</li>' % (os.environ.get('PATH_INFO'))
        print '<li>QUERY_STRING: %s</li>' % (os.environ.get('QUERY_STRING'))
        print '</ul>'
    else:
        print '<p>' + str(exc) + '</p>'

    
def main():
    try:
        req = Request()
    except SystemExit:
        pass
    except (MissingAlbumException,
            UnknownAlbumException,
            EmptyArchiveException,
            InvalidPasswordException,
            ):
        print_exception(False)
    except Exception:
        print_exception(True)


if __name__ == "__main__":
    if os.environ.has_key('DEBUG'):
        test(sys.argv[1], sys.argv[2])
    else:
        main()
