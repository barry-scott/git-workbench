#!/usr/bin/env python3
#
#   package_workbench.py
#
from __future__ import print_function   # need to allow python3 only message

import sys
import os
import time
import shutil
import subprocess
import platform
import glob
import build_log
import build_utils
import package_list_repo

log = build_log.BuildLog()

# setup build_utils
build_utils.log = log
# alias run()
run = build_utils.run
BuildError = build_utils.BuildError

class PackageWorkbench(object):
    valid_cmds = ('srpm-release', 'srpm-testing', 'mock-release', 'mock-testing', 'copr-release', 'copr-testing', 'list-release', 'list-testing')

    def __init__( self ):
        self.KITNAME = 'scm-workbench'

        self.opt_colour = False
        self.opt_verbose = False
        self.opt_kit_xml_preferences = None

        self.copr_repo = None
        self.copr_repo_other = None

        self.cmd = None
        self.opt_release = 'auto'
        self.opt_mock_target = None
        self.opt_arch = None
        self.install = False

    def main( self, argv ):
        try:
            if sys.version_info[0] != 3:
                raise BuildError( '%s requires python3' % (os.path.basename( argv[0] ),) )

            self.parseArgs( argv )
            log.setColour( self.opt_colour )
            self.setupVars()

            if self.cmd in ('srpm-release', 'srpm-testing'):
                self.buildSrpm()

            elif self.cmd in ('mock-testing', 'mock-release'):
                self.buildMock()

            elif self.cmd in ('copr-release', 'copr-testing' ):
                self.buildCopr()

            elif self.cmd in ('list-release', 'list-testing'):
                self.listCopr()

        except KeyboardInterrupt:
            return 2

        except BuildError as e:
            log.error( str(e) )
            return 1

        return 0

    def readVersionInfo( self ):
        # load the version definitions
        vi = {}
        with open( '%s/Builder/version.dat' % (self.BUILDER_TOP_DIR,), 'r' ) as f:
            for line in f:
                line = line.strip()
                if line == '':
                    continue

                if line.startswith( '#' ):
                    continue

                key, value = line.split( '=', 1 )
                vi[ key.strip() ] = value.strip()

        return vi

    def setupVars( self ):
        # expects to be run from the Builder folder
        self.BUILDER_TOP_DIR = os.path.abspath( '..' )

        vi = self.readVersionInfo()

        self.version = '%s.%s.%s' % (vi.get( 'major' ), vi.get( 'minor' ), vi.get( 'patch' ))

        self.MOCK_COPR_REPO_FILENAME = '/etc/yum.repos.d/_copr:copr.fedorainfracloud.org:barryascott:%s.repo' % (self.copr_repo,)

        if self.opt_mock_target is None:
            self.opt_mock_target = 'fedora-%d-%s' % (self.fedoraVersion(), platform.machine())
            log.info( 'Defaulting --mock-target=%s' % (self.opt_mock_target,) )

        self.COPR_REPO_URL = 'https://copr-be.cloud.fedoraproject.org/results/barryascott/%s/%s' % (self.copr_repo, self.opt_mock_target)
        self.COPR_REPO_OTHER_URL = 'https://copr-be.cloud.fedoraproject.org/results/barryascott/%s/%s' % (self.copr_repo_other, self.opt_mock_target)

        if self.opt_release == 'auto':
            all_packages = package_list_repo.listRepo( self.COPR_REPO_URL )
            all_other_packages = package_list_repo.listRepo( self.COPR_REPO_OTHER_URL )

            package_ver = 0
            other_package_ver = 0

            if self.KITNAME in all_packages:
                ver, rel, build_time = all_packages[ self.KITNAME ]
                if ver == self.version:
                    package_ver = int( rel.split('.')[0] )
                    log.info( 'Release %d found in %s' % (package_ver, self.copr_repo) )

            if self.KITNAME in all_other_packages:
                ver, rel, build_time = all_other_packages[ self.KITNAME ]
                if ver == self.version:
                    other_package_ver = int( rel.split('.')[0] )
                    log.info( 'Release %d found in %s' % (package_ver, self.copr_repo_other) )

            self.opt_release = 1 + max( package_ver, other_package_ver )

            log.info( 'Release set to %d' % (self.opt_release,) )

    def parseArgs( self, argv ):
        try:
            args = iter( argv )
            next(args)

            self.cmd = next(args)
            if self.cmd not in self.valid_cmds:
                raise BuildError( 'Unknown command %r - pick on of: %s' %
                                    (self.cmd, ', '.join( self.valid_cmds,)) )

            if self.cmd in ('srpm-release', 'mock-release', 'list-release', 'copr-release'):
                self.copr_repo = 'tools'
                self.copr_repo_other = 'tools-testing'

            elif self.cmd in ('srpm-testing', 'mock-testing', 'list-testing', 'copr-testing'):
                self.copr_repo = 'tools-testing'
                self.copr_repo_other = 'tools'

            while True:
                arg = next(args)
                if arg == '--debug':
                    log.setDebug( True )

                elif arg == '--verbose':
                    self.opt_verbose = True

                elif arg == '--colour':
                    self.opt_colour = True

                elif arg.startswith('--kit-xml-preferences='):
                    self.opt_kit_xml_preferences = arg[len('--kit-xml-preferences='):]

                elif arg.startswith('--release='):
                    self.opt_release = arg[len('--release='):]

                elif arg.startswith('--mock-target='):
                    self.opt_mock_target = arg[len('--mock-target='):]

                elif arg.startswith('--install'):
                    self.install = True

                else:
                    raise BuildError( 'Unknown option %r' % (arg,) )

        except StopIteration:
            pass

    def fedoraVersion( self ):
        with open( '/etc/os-release', 'r' ) as f:
            for line in f:
                if line.startswith( 'VERSION_ID=' ):
                    return int( line.strip()[len('VERSION_ID='):] )

        raise BuildError( 'Expected /etc/os-release to have a VERSION_ID= field' )

    def buildSrpm( self ):
        log.info( 'buildSrpm' )
        run( ('rm', '-rf', 'tmp') )
        run( ('mkdir', '-p', 'tmp') )
        run( ('mkdir', 'tmp/sources') )

        self.makeTarBall()

        if self.opt_kit_xml_preferences is not None:
            log.info( 'Add xml-preferences to sources from %s' % (self.opt_kit_xml_preferences,) )
            shutil.copyfile( self.opt_kit_xml_preferences, os.path.join( 'tmp/sources', os.path.basename( self.opt_kit_xml_preferences ) ) )

        self.ensureMockSetup()
        self.makeSrpm()
        log.info( 'SRPM is %s' % (self.SRPM_FILENAME,) )

    def buildMock( self ):
        log.info( 'buildMock' )
        self.buildSrpm()

        log.info( 'Creating RPM' )
        if self.copr_repo is not None:
            run( ('mock',
                        '--root=%s' % (self.MOCK_TARGET_FILENAME,),
                        '--enablerepo=barryascott-%s' % (self.copr_repo,),
                        '--rebuild',
                        self.SRPM_FILENAME) )
        else:
            run( ('mock',
                        '--root=%s' % (self.MOCK_TARGET_FILENAME,),
                        '--rebuild',
                        self.SRPM_FILENAME) )

        all_bin_kitnames = [
            self.KITNAME,
            ]

        run( ('mkdir','-p', 'built') )

        for bin_kitname in all_bin_kitnames:
            basename = '%s-%s-%s.%s.%s.rpm' % (bin_kitname, self.version, self.opt_release, self.dist_tag, 'noarch')
            src = '%s/RPMS/%s' % (self.MOCK_BUILD_DIR, basename)
            if not os.path.exists( src ):
                raise BuildError( 'Cannot find kit %s' % (src,) )

            log.info( 'Copying %s' % (basename,) )
            shutil.copyfile( src, 'built/%s' % (basename,) )


        log.info( 'Results in %s/built:' % (os.getcwd(),) )

        if self.install:
            log.info( 'Installing RPMs' )

            for bin_kitname in all_bin_kitnames:
                cmd = ('rpm', '-q', bin_kitname)
                p = run( cmd, check=False )
                if p.returncode == 0:
                    run( ('sudo', 'dnf', '-y', 'remove', bin_kitname) )

            cmd = ['sudo', 'dnf', '-y', 'install']
            cmd.extend( glob.glob( 'tmp/%s*.%s.rpm' % (self.KITNAME, self.opt_arch) ) )
            run( cmd )

    def buildCopr( self ):
        log.info( 'buildCopr' )
        # setup vars based on mock config
        self.readMockConfig()

        self.buildSrpm()
        run( ('copr-cli', 'build', '-r', self.opt_mock_target, self.copr_repo, self.SRPM_FILENAME) )

    def listCopr( self ):
        all_packages = package_list_repo.listRepo( self.COPR_REPO_URL )
        print( 'Packages for %s %s' % (self.copr_repo, self.opt_mock_target) )

        now = time.time()

        for name in sorted( all_packages.keys() ):
            ver, rel, build_time = all_packages[ name ]

            build_age = self.formatTimeDelta( now - build_time )

            build_time_str = time.strftime( '%Y-%m-%d %H:%M:%S', time.localtime( build_time ) )
            print( '  %30s: %-8s %-8s %s - %s' % (name, ver, rel, build_time_str, build_age ) )

    def formatTimeDelta( self, age ):
        r, s = divmod( age, 60 )
        r, m = divmod( r, 60 )
        d, h = divmod( r, 24 )

        return '%3dd %2.2d:%2.2d' % (d, h, m)

    def ensureMockSetup( self ):
        log.info( 'Creating mock target file' )
        self.makeMockTargetFile()

        p = run( ('mock', '--root=%s' % (self.MOCK_TARGET_FILENAME,), '--print-root-path'), output=True )

        self.MOCK_ROOT = p.stdout.strip()
        self.MOCK_BUILD_DIR = '%s/builddir/build' % (self.MOCK_ROOT,)

        if os.path.exists( self.MOCK_ROOT ):
            log.info( 'Using existing mock for %s' % (self.opt_mock_target,) )

        else:
            log.info( 'Init mock for %s' % (self.MOCK_TARGET_FILENAME,) )
            run( ('mock', '--root=%s' % (self.MOCK_TARGET_FILENAME,), '--init') )

    def readMockConfig( self ):
        mock_cfg = '/etc/mock/%s.cfg' % (self.opt_mock_target,)
        if not os.path.exists( mock_cfg ):
            raise BuildError( 'Mock CFG files does not exist %s' % (mock_cfg,) )

        with open( mock_cfg, 'r' ) as f:
            # starting with Fedora 31 mock uses the include('template') statement
            config_opts = {'yum_install_command': ''}
            cfg_locals = {'config_opts': config_opts}

            def include( tpl ):
                abs_tpl = os.path.join( '/etc/mock', tpl )
                with open( abs_tpl, 'r' ) as t:
                    tpl_code = compile( t.read(), 'mock_tpl', 'exec' )
                    exec( tpl_code , globals(), cfg_locals)

            cfg_locals['include'] = include

            cfg_code = compile( f.read(), 'mock_cfg', 'exec' )

            exec( cfg_code, globals(), cfg_locals )

        def expandMockCfgVars( key ):
            value = config_opts[ key ]
            value = value.replace( '{{ releasever }}', config_opts[ 'releasever' ] )
            assert '{{' not in value, 'Key %s: Found {{ in %r' % (key, value)
            return value

        # set to match the mock target
        self.opt_arch = config_opts[ 'target_arch' ]
        self.dist_tag = expandMockCfgVars( 'dist' )
        return config_opts

    def makeMockTargetFile( self ):
        self.MOCK_TARGET_FILENAME = 'tmp/%s-%s-%s.cfg' % (self.KITNAME, self.copr_repo, self.opt_mock_target)

        config_opts = self.readMockConfig()

        if 'yum.conf' in config_opts:
            conf_key = 'yum.conf'

        elif 'dnf.conf' in config_opts:
            conf_key = 'dnf.conf'

        else:
            assert False, 'config_opts missing yum.conf or dnf.conf section'

        with open( self.MOCK_COPR_REPO_FILENAME, 'r' ) as f:
            repo = f.read()

            if self.opt_mock_target.startswith( 'epel-' ):
                repo = repo.replace( '/fedora-$releasever-$basearch/', '/epel-$releasever-$basearch/' )

            config_opts[conf_key] += '\n'
            config_opts[conf_key] += repo
            config_opts['root'] = os.path.splitext( os.path.basename( self.MOCK_TARGET_FILENAME ) )[0]

        with open( self.MOCK_TARGET_FILENAME, 'w' ) as f:
            for k in config_opts:
                if k == conf_key:
                    print( '''config_opts['%s'] = """''' % (conf_key,), end='', file=f )
                    print( config_opts[conf_key], file=f )
                    print( '"""', file=f )

                else:
                    print( '''config_opts['%s'] = %r''' % (k, config_opts[k]), file=f )

        # prevent mock from rebuilding the mock cache on each build.
        # mock uses the timestamp on the CFG file and compares to the
        # cache timestamp. Use the timestamp of the input cfg to avoid
        # rebuilding the cache unless the original CFG file changes.
        mock_cfg = '/etc/mock/%s.cfg' % (self.opt_mock_target,)
        st = os.stat( mock_cfg )
        os.utime( self.MOCK_TARGET_FILENAME, (st.st_atime, st.st_mtime) )

    def makeTarBall( self ):
        self.KIT_BASENAME = '%s-%s' % (self.KITNAME, self.version)

        log.info( 'Exporting source code' )

        cmd = '(cd ${BUILDER_TOP_DIR}; git archive --format=tar --prefix=%s/ master) | tar xf - -C tmp ' % (self.KIT_BASENAME,)
        run( cmd )

        p = run( ('git', 'show-ref', '--head', '--hash', 'head'), output=True, cwd=os.environ['BUILDER_TOP_DIR'] )

        with open( os.path.join( 'tmp', self.KIT_BASENAME, 'Builder/commit_id.txt' ), 'w' ) as f:
            f.write( p.stdout )

        run( (os.environ['PYTHON'], '-u',
                '%s/Source/make_wb_scm_version.py' % (self.BUILDER_TOP_DIR,),
                '%s/Builder/version.dat' % (self.BUILDER_TOP_DIR,),
                'tmp/scm-workbench-%s/Source/Scm/wb_scm_version.py' % (self.version,)) )

        run( ('tar', 'czf', 'sources/%s.tar.gz' % (self.KIT_BASENAME,), self.KIT_BASENAME), cwd='tmp' )

    def makeSrpm( self ):
        log.info( 'makeSrpm' )
        log.info( 'Creating %s.spec' % (self.KITNAME,) )
        import package_rpm_specfile
        package_rpm_specfile.createRpmSpecFile( self, 'tmp/%s.spec' % (self.KITNAME,) )

        log.info( 'Creating SRPM for %s' % (self.KIT_BASENAME,) )

        run( ('mock',
                '--root=%s' % (self.MOCK_TARGET_FILENAME,),
                '--buildsrpm',
                '--spec', 'tmp/%s.spec' % (self.KITNAME,),
                '--sources', 'tmp/sources') )

        SRPM_BASENAME = '%s-%s.%s' % (self.KIT_BASENAME, self.opt_release, self.dist_tag)
        self.SRPM_FILENAME = 'tmp/%s.src.rpm' % (SRPM_BASENAME,)

        src = '%s/SRPMS/%s.src.rpm' % (self.MOCK_BUILD_DIR, SRPM_BASENAME)
        log.info( 'copy %s %s' % (src, self.SRPM_FILENAME) )
        shutil.copyfile( src, self.SRPM_FILENAME )

if __name__ == '__main__':
    sys.exit( PackageWorkbench().main( sys.argv ) )
