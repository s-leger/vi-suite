import bpy, os, sys, multiprocessing, mathutils, bmesh, datetime, colorsys, bgl, blf, shlex
from collections import OrderedDict
from subprocess import Popen, PIPE, STDOUT
from numpy import array, digitize, amax, amin, average, zeros, inner
from numpy import sum as nsum
from math import sin, cos, asin, acos, pi, isnan, tan
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import IntProperty, StringProperty, EnumProperty, FloatProperty, BoolProperty, FloatVectorProperty
try:
    import matplotlib
    matplotlib.use('Qt4Agg', force = True)
    import matplotlib.pyplot as plt
    import matplotlib.colors as colors
    from .windrose import WindroseAxes
    mp = 1
except Exception as e:
    print(e)
    mp = 0

dtdf = datetime.date.fromordinal

def cmap(cm):
    cmdict = {'hot': 'livi', 'grey': 'shad'}
    for i in range(20):       
        if not bpy.data.materials.get('{}#{}'.format(cmdict[cm], i)):
            bpy.data.materials.new('{}#{}'.format(cmdict[cm], i))
        bpy.data.materials['{}#{}'.format(cmdict[cm], i)].diffuse_color = colorsys.hsv_to_rgb(0.75 - 0.75*(i/19), 1, 1) if cm == 'hot' else colorsys.hsv_to_rgb(1, 0, (i/19))
        if cm == 'grey':
            bpy.data.materials['{}#{}'.format(cmdict[cm], i)].diffuse_intensity = i/19
        bpy.data.materials['{}#{}'.format(cmdict[cm], i)].specular_intensity = 0
        bpy.data.materials['{}#{}'.format(cmdict[cm], i)].specular_color = (0, 0, 0)
        bpy.data.materials['{}#{}'.format(cmdict[cm], i)].use_shadeless = 1

def radmat(self, scene):
    radname = self.name.replace(" ", "_")         
    radentry = '# ' + ('plastic', 'glass', 'dielectric', 'translucent', 'mirror', 'light', 'metal', 'antimatter', 'bsdf', 'custom')[int(self.radmatmenu)] + ' material\n' + \
            '{} {} {}\n'.format('void', ('plastic', 'glass', 'dielectric', 'trans', 'mirror', 'light', 'metal', 'antimatter', 'bsdf', 'custom')[int(self.radmatmenu)], radname) + \
           {'0': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f}\n'.format(self.radcolour, self.radspec, self.radrough), 
            '1': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format(self.radcolour), 
            '2': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} 0\n'.format(self.radcolour, self.radior),
            '3': '0\n0\n7 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f} {3:.3f} {4:.3f}\n'.format(self.radcolour, self.radspec, self.radrough, self.radtrans, self.radtranspec), 
            '4': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format(self.radcolour),
            '5': '0\n0\n3 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n'.format([c * self.radintensity for c in self.radcolour]), 
            '6': '0\n0\n5 {0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1:.3f} {2:.3f}\n'.format(self.radcolour, self.radspec, self.radrough), 
            '7': '1 void\n0\n0\n', '8': '1 void\n0\n0\n', '9': '1 void\n0\n0\n'}[self.radmatmenu] + '\n'

    if self.radmatmenu == '8' and self.get('bsdf') and self['bsdf'].get('xml'):
        radentry = ''
#        bsdfxml = os.path.join(scene['viparams']['newdir'], 'bsdfs', '{}.xml'.format(self.name))
#        with open(bsdfxml, 'w') as bsdffile:
#            bsdffile.write(self['bsdf']['xml'].decode())
#        radentry = 'void BSDF {0}\n16 0 {1} 0 0 1 . -rx {2[0]} -ry {2[1]} -rz {2[2]} -t {3[0]} {3[1]} {3[2]}\n0\n0\n\n'.format(radname, bsdfxml, self['bsdf']['rotation'], self['bsdf']['translation'])
    if self.radmatmenu == '9':
        if self.name in [t.name for t in bpy.data.texts]:
            radentry = bpy.data.texts[self.name].as_string()+'\n\n'
    self['radentry'] = radentry
    return(radentry)
    
def radbsdf(self, radname, fi, rot, trans):
    fmat = self.data.materials[self.data.polygons[fi].material_index]
    pdepth = fmat['bsdf']['proxy_depth'] if self.bsdf_proxy else 0 
    bsdfxml = self.data.materials[self.data.polygons[fi].material_index]['bsdf']['xml']
    radname = '{}_{}_{}'.format(fmat.name, self.name, fi)
#    with open(bsdfxml, 'w') as bsdffile:
#        bsdffile.write(self['bsdf']['xml'].decode())
    radentry = 'void BSDF {0}\n16 {4:.3f} {1} 0 0 1 . -rx {2[0]:.3f} -ry {2[1]:.3f} -rz {2[2]:.3f} -t {3[0]:.3f} {3[1]:.3f} {3[2]:.3f}\n0\n0\n\n'.format(radname, bsdfxml, rot, trans, pdepth)
    return radentry
    
        
def rtpoints(self, bm, offset, frame):    
    geom = bm.verts if self['cpoint'] == '1' else bm.faces 
    cindex = geom.layers.int['cindex']
    for gp in geom:
        gp[cindex] = 0 
    geom.ensure_lookup_table()
    resfaces = [face for face in bm.faces if self.data.materials[face.material_index].mattype == '1']
    self['cfaces'] = [face.index for face in resfaces]
       
    if self['cpoint'] == '0': 
        gpoints = resfaces
        csfc = [face.calc_center_median() for face in gpoints]                      
        self['rtpoints'][frame] = ''.join(['{0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1[0]:.3f} {1[1]:.3f} {1[2]:.3f} \n'.format([csfc[fi][i] + offset * f.normal.normalized()[i] for i in range(3)], f.normal[:]) for fi, f in enumerate(gpoints)])
        self['cverts'], self['lisenseareas'][frame] = [], [f.calc_area() for f in gpoints]       

    elif self['cpoint'] == '1': 
        gis = sorted(set([item.index for sublist in [face.verts[:] for face in resfaces] for item in sublist]))
        gpoints = [geom[gi] for gi in gis]
        self['rtpoints'][frame]  = ''.join(['{0[0]:.3f} {0[1]:.3f} {0[2]:.3f} {1[0]:.3f} {1[1]:.3f} {1[2]:.3f} \n'.format([gp.co[i] + offset * gp.normal[i] for i in range(3)], gp.normal) for gp in gpoints])
        self['cverts'], self['lisenseareas'][frame] = gp.index, [vertarea(bm, gp) for gp in gpoints]
    
    for g, gp in enumerate(gpoints):
        gp[cindex] = g + 1
        
    self['rtpnum'] = g + 1
                    
def regresults(scene, frames, simnode, res):    
    for i, f in enumerate(frames):
        simnode['maxres'][str(f)] = amax(res[i])
        simnode['minres'][str(f)] = amin(res[i])
        simnode['avres'][str(f)] = average(res[i])
    scene.vi_leg_max, scene.vi_leg_min = max(simnode['maxres'].values()), min(simnode['minres'].values()) 

def clearlayers(bm):
    while bm.faces.layers.float:
        bm.faces.layers.float.remove(bm.faces.layers.float[0])
    while bm.verts.layers.float:
        bm.verts.layers.float.remove(bm.verts.layers.float[0])

def cbdmmtx(self, scene, locnode, export_op):
    os.chdir(scene['viparams']['newdir'])        
    if self['epwbase'][1] in (".epw", ".EPW"):
        with open(locnode.weather, "r") as epwfile:
            epwlines = epwfile.readlines()
            self['epwyear'] = epwlines[8].split(",")[0]
        Popen(("epw2wea", locnode.weather, "{}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])))).wait()
        if self.startmonth != 1 or self.endmonth != 12:
            with open("{}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'r') as weafile:
                wealines = weafile.readlines()
                weaheader = [line for line in wealines[:6]]
                wearange = [line for line in wealines[6:] if int(line.split()[0]) in range (self.startmonth, self.endmonth + 1)]
            with open("{}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'w') as weafile:
                [weafile.write(line) for line in weaheader + wearange]
        gdmcmd = ("gendaymtx -m 1 {} {}".format(('', '-O1')[self['watts']], "{0}.wea".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0]))))
        with open("{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0])), 'w') as mtxfile:
            Popen(gdmcmd.split(), stdout = mtxfile, stderr=STDOUT).communicate()
        with open("{}-whitesky.oct".format(scene['viparams']['filebase']), 'w') as wsfile:
            oconvcmd = "oconv -w -"
            Popen(shlex.split(oconvcmd), stdin = PIPE, stdout = wsfile).communicate(input = self['whitesky'].encode('utf-8'))
        return "{}.mtx".format(os.path.join(scene['viparams']['newdir'], self['epwbase'][0]))
    else:
        export_op.report({'ERROR'}, "Not a valid EPW file")
        return ''

def cbdmhdr(node, scene):
    targethdr = os.path.join(scene['viparams']['newdir'], node['epwbase'][0]+"{}.hdr".format(('l', 'w')[node['watts']]))
    latlonghdr = os.path.join(scene['viparams']['newdir'], node['epwbase'][0]+"{}p.hdr".format(('l', 'w')[node['watts']]))
    skyentry = hdrsky(targethdr)

    if not os.path.isfile(targethdr):
        vecvals, vals = mtx2vals(open(node['mtxfile'], 'r').readlines(), datetime.datetime(2010, 1, 1).weekday(), '')
        pcombfiles = ''.join(["ps{}.hdr ".format(i) for i in range(146)])
        vwcmd = "vwrays -ff -x 600 -y 600 -vta -vp 0 0 0 -vd 0 1 0 -vu 0 0 1 -vh 360 -vv 360 -vo 0 -va 0 -vs 0 -vl 0"
        rcontribcmd = "rcontrib -bn 146 -fo -ab 0 -ad 1 -n {} -ffc -x 600 -y 600 -ld- -V+ -f tregenza.cal -b tbin -o p%d.hdr -m sky_glow {}-whitesky.oct".format(scene['viparams']['nproc'], scene['viparams']['filename'])
        vwrun = Popen(vwcmd.split(), stdout = PIPE)
        Popen(rcontribcmd.split(), stdin = vwrun.stdout).wait()
    
        for j in range(146):
            with open("ps{}.hdr".format(j), 'w') as psfile:
                Popen("pcomb -s {0} p{1}.hdr".format(vals[j], j).split(), stdout = psfile).wait()
        with open(targethdr, 'w') as epwhdr:
            Popen("pcomb -h {}".format(pcombfiles).split(), stdout = epwhdr).wait()
        [os.remove(os.path.join(scene['viparams']['newdir'], 'p{}.hdr'.format(i))) for i in range (146)]
        [os.remove(os.path.join(scene['viparams']['newdir'], 'ps{}.hdr'.format(i))) for i in range (146)]
        node.hdrname = targethdr

    if node.hdr and not os.path.isfile(latlonghdr):
        with open('{}.oct'.format(os.path.join(scene['viparams']['newdir'], node['epwbase'][0])), 'w') as hdroct:
            Popen(shlex.split("oconv -w - "), stdin = PIPE, stdout=hdroct, stderr=STDOUT).communicate(input = skyentry.encode('utf-8'))
        cntrun = Popen('cnt 750 1500'.split(), stdout = PIPE)
        rcalcrun = Popen('rcalc -f {} -e XD=1500;YD=750;inXD=0.000666;inYD=0.001333'.format(os.path.join(scene.vipath, 'Radfiles', 'lib', 'latlong.cal')).split(), stdin = cntrun.stdout, stdout = PIPE)
        with open(latlonghdr, 'w') as panohdr:
            rtcmd = 'rtrace -n {} -x 1500 -y 750 -fac {}.oct'.format(scene['viparams']['nproc'], os.path.join(scene['viparams']['newdir'], node['epwbase'][0]))
            Popen(rtcmd.split(), stdin = rcalcrun.stdout, stdout = panohdr)
    return skyentry

def retpmap(node, frame, scene):
    pportmats = ' '.join([mat.name.replace(" ", "_") for mat in bpy.data.materials if mat.pport and mat.get('radentry')])
    ammats = ' '.join([mat.name.replace(" ", "_") for mat in bpy.data.materials if mat.mattype == '1' and mat.radmatmenu == '7' and mat.get('radentry')])
    pportentry = '-apo {}'.format(pportmats) if pportmats else ''
    amentry = '-aps {}'.format(ammats) if ammats else ''
    cpentry = '-apc {}-{}.cpm {}'.format(scene['viparams']['filebase'], frame, node.pmapcno) if node.pmapcno else ''
    cpfileentry = '-ap {}-{}.cpm 50'.format(scene['viparams']['filebase'], frame) if node.pmapcno else ''  
    return amentry, pportentry, cpentry, cpfileentry     

def setscenelivivals(scene):
    scene['liparams']['maxres'], scene['liparams']['minres'], scene['liparams']['avres'] = {}, {}, {}
    if scene['viparams']['visimcontext'] == 'LiVi Basic':
        udict = {'0': 'Lux', '1': "W/m"+ u'\u00b2', '2': 'DF (%)'}
        scene['liparams']['unit'] = udict[scene.li_disp_basic]
    if scene['viparams']['visimcontext'] == 'LiVi CBDM' and 'UDI' in scene['liparams']['unit']:
        udict = {'0': 'UDI-f (%)', '1': 'UDI-s (%)', '2': 'UDI-a (%)', '3': 'UDI-e (%)'}
        scene['liparams']['unit'] = udict[scene.li_disp_udi]
    if scene['viparams']['visimcontext'] == 'LiVi Compliance':        
        udict = {'0': 'DF (%)', '1': 'Sky View'}
        scene['liparams']['unit'] = udict[scene.li_disp_sv]
    olist = [scene.objects[on] for on in scene['liparams']['shadc']] if scene['viparams']['visimcontext'] == 'Shadow' else [scene.objects[on] for on in scene['liparams']['livic']]
    unitdict = {'Lux': 'illu', "W/m"+ u'\u00b2': 'irrad', 'DF (%)': 'df', 'Sky View': 'sv', 'kLuxHours': 'res', u'kWh/m\u00b2': 'res', 'DA (%)': 'da', 'UDI-f (%)': 'low', 'UDI-s (%)': 'sup', 'UDI-a (%)': 'auto', 'UDI-e (%)': 'high', '% Sunlit': 'res'}
    for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
        scene['liparams']['maxres'][str(frame)] = max([o['omax']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
        scene['liparams']['minres'][str(frame)] = min([o['omin']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
        scene['liparams']['avres'][str(frame)] = sum([o['oave']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])/len([o['oave']['{}{}'.format(unitdict[scene['liparams']['unit']], frame)] for o in olist])
    scene.vi_leg_max = max(scene['liparams']['maxres'].values())
    scene.vi_leg_min = min(scene['liparams']['minres'].values())
    
def rettree(scene, obs):
    bmob = bmesh.new()
    for soi, so in enumerate(obs):
        btemp = bpy.data.meshes.new("temp")
        bmtemp = bmesh.new()
        bmtemp.from_mesh(so.data)
        bmtemp.transform(so.matrix_world)
        delfaces = [face for face in bmtemp.faces if so.data.materials[face.material_index].mattype == '2']
        bmesh.ops.delete(bmtemp, geom = delfaces, context = 5)
        bmtemp.to_mesh(btemp)
        bmob.from_mesh(btemp)
        bpy.data.meshes.remove(btemp)
    tree = BVHTree.FromBMesh(bmob)
    bmob.free()
    bmtemp.free()
    return tree

def progressfile(scene, starttime, calcsteps, curres, action):   
    if os.path.isfile(os.path.join(scene['viparams']['newdir'], 'viprogress')):
        with open(os.path.join(scene['viparams']['newdir'], 'viprogress'), 'r') as pfile:
            if 'CANCELLED' in pfile.read():
                if action != 'clear':
                    return 'CANCELLED'
            
    with open(os.path.join(scene['viparams']['newdir'], 'viprogress'), 'w') as pfile:
        if action == 'clear':
            pfile.write('STARTING')
        else:
            dt = (datetime.datetime.now() - starttime)/calcsteps.index(curres) * (20 - calcsteps.index(curres))
            pfile.write('{} {}'.format(5 * calcsteps.index(curres), datetime.timedelta(seconds = dt.seconds)))
        
def progressbar(file):
    kivytext = "from kivy.app import App \n\
from kivy.clock import Clock \n\
from kivy.uix.progressbar import ProgressBar\n\
from kivy.uix.boxlayout import BoxLayout\n\
from kivy.uix.button import Button\n\
from kivy.uix.label import Label\n\
from kivy.config import Config\n\
Config.set('graphics', 'width', '500')\n\
Config.set('graphics', 'height', '200')\n\
\n\
class CancelButton(Button):\n\
    def on_touch_down(self, touch):\n\
        if 'button' in touch.profile:\n\
            if self.collide_point(*touch.pos):\n\
                with open('/home/ryan/Store/Blender/lividemo/viprogress', 'w') as pffile:\n\
                    pffile.write('CANCELLED')\n\
                App.get_running_app().stop()\n\
        else:\n\
            return\n\
\n\
class Calculating(App):\n\
    bl = BoxLayout(orientation='vertical')\n\
    rpb = ProgressBar()\n\
    label = Label(text=' 0% Complete', font_size=20)\n\
    button = CancelButton(text='Cancel', font_size=20)\n\
    bl.add_widget(rpb)\n\
    bl.add_widget(label)\n\
    bl.add_widget(button)\n\
\n\
    def build(self):\n\
        refresh_time = 1\n\
        Clock.schedule_interval(self.timer, refresh_time)\n\
        return self.bl\n\
\n\
    def timer(self, dt):\n\
        with open('"+file+"', 'r') as pffile:\n\
            try:    (percent, tr) = pffile.readlines()[0].split()\n\
            except: percent, tr = 0, 'Not known'\n\
        self.rpb.value = int(percent)\n\
        self.label.text = '{}% Complete - Time remaining: {}'.format(percent, tr)\n\
\n\
if __name__ == '__main__':\n\
    Calculating().run()\n"

    with open(file+".py", 'w') as kivyfile:
        kivyfile.write(kivytext)
    return Popen([bpy.app.binary_path_python, file+".py"])
    
def basiccalcapply(self, scene, frames, rtcmds, simnode, oi, starttime, onum, tpoints, sstep):    
    reslists = []
    fnum = len(frames)
    calcno = fnum * tpoints
    calcsteps = [int(i * calcno/20) for i in range(0, 21)]
    bm = bmesh.new()
    bm.from_mesh(self.data)
    bm.transform(self.matrix_world)
    self['omax'], self['omin'], self['oave'] = {}, {}, {}
    clearlayers(bm)
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    cindex = geom.layers.int['cindex']

    for f, frame in enumerate(frames):
        geom.layers.float.new('irrad{}'.format(frame))
        geom.layers.float.new('illu{}'.format(frame))
        geom.layers.float.new('df{}'.format(frame))
        geom.layers.float.new('res{}'.format(frame))
        irradres = geom.layers.float['irrad{}'.format(frame)]
        illures = geom.layers.float['illu{}'.format(frame)]
        dfres = geom.layers.float['df{}'.format(frame)]
        res =  geom.layers.float['res{}'.format(frame)]
        
        if str(frame) in self['rtpoints']:
            rtframe = frame
        else:
            kints = [int(k) for k in self["rtpoints"].keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        
#        with open(os.path.join(scene['viparams']['newdir'], 'rtout'), 'w') as rtout:
#            rtp.write(self["rtpoints"][str(rtframe)])
#        with open(os.path.join(scene['viparams']['newdir'], 'rtptemp'), 'r') as rtp:
        rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True).communicate(input = self["rtpoints"][str(rtframe)])    
#        for i in range(100):
#            print(rtrun.poll())
#            time.sleep(1)
#        with open(os.path.join(scene['viparams']['newdir'], 'rtout'), 'r') as rtout:    
        reslines = [[float(rv) for rv in r.split('\t')[:3]] for r in rtrun[0].splitlines()]    
        resirrad = [0.26 * r[0] + 0.67 * r[1] + 0.065 * r[2] for r in reslines]
        resillu = [47.4*r[0]+120*r[1]+11.6*r[2] for r in reslines]
        resdf = [r * 0.01 for r in resillu]
        self['omax']['irrad{}'.format(frame)] = max(resirrad)
        self['omax']['illu{}'.format(frame)] =  max(resillu)
        self['omax']['df{}'.format(frame)] =  max(resdf)
        self['omin']['irrad{}'.format(frame)] = min(resirrad)
        self['omin']['illu{}'.format(frame)] = min(resillu)
        self['omin']['df{}'.format(frame)] = min(resdf)
        self['oave']['irrad{}'.format(frame)] = sum(resirrad)/len(resirrad)
        self['oave']['illu{}'.format(frame)] = sum(resillu)/len(resillu)
        self['oave']['df{}'.format(frame)] = sum(resdf)/len(resdf)    

        for g in [g for g in geom if g[cindex] > 0]:
            g[irradres] = resirrad[g[cindex] - 1]
            g[illures] = resillu[g[cindex] - 1]
            g[dfres] = resdf[g[cindex] - 1]
            g[res] = g[illures]
                
        posis = [v.co for v in bm.verts if v[cindex] > 0] if self['cpoint'] == '1' else [f.calc_center_bounds() for f in bm.faces if f[cindex] > 1]
        reslists.append([str(frame), 'Position', self.name, 'X', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Position', self.name, 'Y', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Position', self.name, 'Z', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Lighting', self.name, 'Illuminance(lux)', ' '.join([str(g[illures]) for g in geom if g[cindex] > 0])])
        reslists.append([str(frame), 'Lighting', self.name, 'DF (%)', ' '.join([str(g[dfres]) for g in geom if g[cindex] > 0])])
        reslists.append([str(frame), 'Lighting', self.name, 'Irradiance (W/m2)', ' '.join([str(g[irradres]) for g in geom if g[cindex] > 0])])
        print('Radiance simulation {:.0f}% complete'.format((oi + (f+1)/fnum)/onum * 100))
        

    bm.transform(self.matrix_world.inverted())
    bm.to_mesh(self.data)
    bm.free()
    
def lhcalcapply(self, scene, frames, rtcmds, simnode, oi, starttime, onum, tpoints, sstep):
    reslists = []
    fnum = len(frames)
    calcno = fnum * tpoints
    calcsteps = [int(i * calcno/20) for i in range(0, 21)]
    bm = bmesh.new()
    bm.from_mesh(self.data)
    self['omax'], self['omin'], self['oave'] = {}, {}, {}
    clearlayers(bm)
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    cindex = geom.layers.int['cindex']
    for f, frame in enumerate(frames):        
        if str(frame) in self['rtpoints']:
            rtframe = frame
        else:
            kints = [int(k) for k in self["rtpoints"].keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=STDOUT).communicate(input = self["rtpoints"][str(rtframe)].encode('utf-8'))
    
        reslines = [[float(rv) for rv in r.split('\t')[:3]] for r in rtrun[0].decode().splitlines()] 
        if scene['liparams']['unit'] == 'kLuxHours':
            resvals = [(47.4*r[0]+120*r[1]+11.6*r[2]) * 0.001 for r in reslines]
        elif scene['liparams']['unit'] == u'kWh/m\u00b2':
            resvals = [(0.26 * r[0] + 0.67 * r[1] + 0.065 * r[2]) * 0.001 for r in reslines]
        self['omax']['res{}'.format(frame)] = max(resvals)
        self['omin']['res{}'.format(frame)] = min(resvals)
        self['oave']['res{}'.format(frame)] = sum(resvals)/len(resvals)
        geom.layers.float.new('res{}'.format(frame))
        res =  geom.layers.float['res{}'.format(frame)]
        for g in [g for g in geom if g[cindex] > 0]:
            g[res] = resvals[g[cindex] - 1]  
            sstep += 1
            print(sstep, calcsteps)
            if sstep in calcsteps:
                if progressfile(scene, starttime, calcsteps, sstep, 'run') == 'CANCELLED':
                    return 'CANCELLED'
        posis = [v.co for v in bm.verts if v[cindex] > 0] if self['cpoint'] == '1' else [f.calc_center_bounds() for f in bm.faces if f[cindex] > 1]
        reslists.append([str(frame), 'Position', self.name, 'X', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Position', self.name, 'Y', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Position', self.name, 'Z', ' '.join([str(p[0]) for p in posis])])
        reslists.append([str(frame), 'Lighting', self.name, scene['liparams']['unit'], ' '.join([str(g[res]) for g in geom if g[cindex] > 0])])
        print('Radiance simulation {:.0f}% complete'.format((oi + (f+1)/fnum)/onum * 100))
    
    bm.transform(self.matrix_world.inverted())
    bm.to_mesh(self.data)
    bm.free()
    
def lividisplay(self, scene): 
    unitdict = {'Lux': 'illu', u'W/m\u00b2': 'irrad', 'DF (%)': 'df', 'DA (%)': 'res', 'UDI-f (%)': 'low', 'UDI-s (%)': 'sup', 'UDI-a (%)': 'auto', 'UDI-e (%)': 'high',
                'Sky View': 'sv', 'kLuxHours': 'res', u'kWh/m\u00b2': 'res', '% Sunlit': 'res'}
    frames = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
    if len(frames) > 1:
        if not self.data.animation_data:
            self.data.animation_data_create()
        
        self.data.animation_data.action = bpy.data.actions.new(name="LiVi MI")
        fis = [str(face.index) for face in self.data.polygons]
        lms = {fi: self.data.animation_data.action.fcurves.new(data_path='polygons[{}].material_index'.format(fi)) for fi in fis}
        for fi in fis:
            lms[fi].keyframe_points.add(len(frames))

    for f, frame in enumerate(frames):  
        bm = bmesh.new()
        bm.from_mesh(self.data)
        geom = bm.verts if scene['liparams']['cp'] == '1' else bm.faces  
        livires = geom.layers.float['{}{}'.format(unitdict[scene['liparams']['unit']], frame)]
        res = geom.layers.float['res{}'.format(frame)]
        oreslist = [g[livires] for g in geom]
        self['omax'][str(frame)], self['omin'][str(frame)], self['oave'][str(frame)] = max(oreslist), min(oreslist), sum(oreslist)/len(oreslist)
        smaxres, sminres =  max(scene['liparams']['maxres'].values()), min(scene['liparams']['minres'].values())
        if smaxres > sminres:
            vals = array([(f[livires] - sminres)/(smaxres - sminres) for f in bm.faces]) if scene['liparams']['cp'] == '0' else \
                    ([(sum([vert[livires] for vert in f.verts])/len(f.verts) - sminres)/(smaxres - sminres) for f in bm.faces])
        else:
            vals = array([max(scene['liparams']['maxres'].values()) for x in range(len(bm.faces))])
            
        if livires != res:
            for g in geom:
                g[res] = g[livires]        
        bins = array([0.05*i for i in range(1, 20)])
        nmatis = digitize(vals, bins)
        bm.to_mesh(self.data)
        bm.free()
        if len(frames) == 1:
            self.data.polygons.foreach_set('material_index', nmatis)
        elif len(frames) > 1:
            for fii, fi in enumerate(fis):
                lms[fi].keyframe_points[f].co = frame, nmatis[fii]  
            
def retcrits(simnode, matname):
    mat = bpy.data.materials[matname]
    if simnode['coptions']['canalysis'] == '0':
        if simnode['coptions']['bambuild'] in ('0', '5'):
            if not mat.gl_roof:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']] 
            else:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]

        elif simnode['coptions']['bambuild'] == '1':
            if not mat.gl_roof:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
            else:
                crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit= [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]

        elif simnode['coptions']['bambuild'] == '2':
            crit = [['Percent', 80, 'DF', 2, '1']] if mat.hspacemenu == '0' else [['Percent', 80, 'DF', 3, '2']]
            ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Min', 100, 'PDF', 1.6, '0.75'], ['Min', 100, 'PDF', 1.2, '0.75']]
   
        elif simnode['coptions']['bambuild'] == '3':
            if mat.brspacemenu == '0':
                crit = [['Percent', 80, 'DF', 2, '1'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]

            elif mat.brspacemenu == '1':
                crit = [['Percent', 80, 'DF', 1.5, '1'], ['Percent', 100, 'Skyview', 1, '0.75']]
                ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]

            elif mat.brspacemenu == '2':
                if not mat.gl_roof:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']]
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
                else:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'],['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']] 
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 2.1, '0.75']]

        elif simnode['coptions']['bambuild'] == '4':
            if mat.respacemenu == '0':
                crit = [['Percent', 35, 'PDF', 2, '1']]
                ecrit = [['Percent', 50, 'PDF', 2, '1']]

            elif mat.respacemenu == '1':
                if not mat.gl_roof:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.4, '0.5'], ['Min', 100, 'PDF', 0.8, '0.5'], ['Percent', 80, 'Skyview', 1, '0.75']] 
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 1.6, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'], ['Min', 100, 'PDF', 1.2, '0.75']]
   
                else:
                    crit = [['Percent', 80, 'DF', 2, '1'], ['Ratio', 100, 'Uni', 0.7, '0.5'], ['Min', 100, 'PDF', 1.4, '0.5'], ['Percent', 100, 'Skyview', 1, '0.75']]
                    ecrit = [['Percent', 80, 'DF', 4, '1'], ['Min', 100, 'PDF', 2.8, '0.75']] if simnode['coptions']['storey'] == '0' else [['Percent', 80, 'DF', 3, '1'],['Min', 100, 'PDF', 2.1, '0.75']] 

    elif simnode['coptions']['canalysis'] == '1':
        crit = [['Average', 100, 'DF', 2, '1'], ['Percent', 80, 'Skyview', 1, '0.75']] if mat.crspacemenu == '0' else [['Average', 100, 'DF', 1.5, '1'], ['Percent', 80, 'Skyview', 1, '0.75']]
        ecrit = []
    elif simnode['coptions']['canalysis'] == '2':
        crit = [['Percent', 75, 'FC', 108, '1'], ['Percent', 75, 'FC', 5400, '1'], ['Percent', 90, 'FC', 108, '1'], ['Percent', 90, 'FC', 5400, '1']]
        ecrit = []
        
    return [[c[0], str(c[1]), c[2], str(c[3]), c[4]] for c in crit[:]], [[c[0], str(c[1]), c[2], str(c[3]), c[4]] for c in ecrit[:]]
    
def compcalcapply(self, scene, frames, rtcmds, simnode):  
    self['compmat'] = [material.name for material in self.data.materials if material.mattype == '1'][0]
    self['omax'], self['omin'], self['oave'] = {}, {}, {}
    self['crit'], self['ecrit'] = retcrits(simnode, self['compmat'])
    comps, ecomps =  {str(f): [] for f in frames}, {str(f): [] for f in frames}
    crits, dfpass, edfpass = [], {str(f): 0 for f in frames}, {str(f): 0 for f in frames} 
    selobj(scene, self)
    bm = bmesh.new()
    bm.from_mesh(self.data)
    clearlayers(bm)
    geom = bm.verts if simnode['goptions']['cp'] == '1' else bm.faces
    
    for f, frame in enumerate(frames):
        if str(frame) in self['rtpoints']:
            rtframe = frame
        else:
            kints = [int(k) for k in self["rtpoints"].keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
                
        rtrun = Popen(rtcmds[f].split(), stdin = PIPE, stdout=PIPE, stderr=STDOUT).communicate(input = self["rtpoints"][str(rtframe)].encode('utf-8'))
        reslines = [[float(rv) for rv in r.split('\t')[:3]] for r in rtrun[0].decode().splitlines()]    
        resillu = [47.4*r[0]+120*r[1]+11.6*r[2] for r in reslines]
        resdf = [r * 0.01 for r in resillu]
        reslen = len(resdf)
        svcmd = "rtrace -n {0} -w {1} -h -ov -I {2}-{3}.oct ".format(scene['viparams']['nproc'], '-ab 1 -ad 8192 -aa 0 -ar 512 -as 1024 -lw 0.0002', scene['viparams']['filebase'], frame)    
        rtrun = Popen(svcmd.split(), stdin = PIPE, stdout=PIPE, stderr=STDOUT).communicate(input = self["rtpoints"][str(rtframe)].encode('utf-8'))                 
        reslines = [[float(rv) for rv in r.split('\t')[:3]] for r in rtrun[0].decode().splitlines()] 
        ressv = [(0, 1)[sum(r[:3]) > 0] for r in reslines]
    
        self['omax']['df{}'.format(frame)] = max(resdf)
        self['omin']['df{}'.format(frame)] = min(resdf)
        self['oave']['df{}'.format(frame)] = sum(resdf)/len(resdf)
        self['omax']['sv{}'.format(frame)] =  1.0
        self['omin']['sv{}'.format(frame)] = 0.0
        self['oave']['sv{}'.format(frame)] = sum(ressv)/len(ressv)
        cindex = geom.layers.int['cindex']
        geom.layers.float.new('sv{}'.format(frame))
        geom.layers.float.new('df{}'.format(frame))
        geom.layers.float.new('res{}'.format(frame))
        dfreslayer = geom.layers.float['df{}'.format(frame)]
        svreslayer = geom.layers.float['sv{}'.format(frame)]
        res = geom.layers.float['res{}'.format(frame)]
        for g in [g for g in geom if g[cindex] > 0]:
            g[dfreslayer] = resdf[g[cindex] - 1]
            g[svreslayer] = ressv[g[cindex] - 1]
            g[res] = (resdf[g[cindex] - 1], ressv[g[cindex] - 1])[int(scene.li_disp_sv)]
        
        dftotarea, dfpassarea, edfpassarea, edftotarea = 0, 0, 0, 0
        oareas = self['lisenseareas'][str(frame)]
        oarea = sum(oareas)
        passarea = 0

        for c in self['crit']:
            if c[0] == 'Percent':
                if c[2] == 'DF':
                    dfpass[str(frame)] = 1
                    dfpassarea = dfpassarea + oarea if sum(resdf)/reslen > float(c[3]) else dfpassarea
                    comps[str(frame)].append((0, 1)[sum(resdf)/reslen > float(c[3])])
                    comps[str(frame)].append(sum(resdf)/reslen)
                    dftotarea += oarea
                    
                if c[2] == 'PDF':
                    dfpass[str(frame)] = 1
                    dfpassarea = sum([area for p, area in enumerate(oareas) if resdf[p] > int(c[3])])
                    comps[str(frame)].append((0, 1)[dfpassarea > float(c[1])*oarea/100])
                    comps[str(frame)].append(100*dfpassarea/oarea)
                    dftotarea += oarea
    
                elif c[2] == 'Skyview':
                    passarea = sum([area for p, area in enumerate(oareas) if ressv[p] > 0])
                    comps[str(frame)].append((0, 1)[passarea >= float(c[1])*oarea/100])
                    comps[str(frame)].append(100*passarea/oarea)
                    passarea = 0
    
            elif c[0] == 'Min':
                comps[str(frame)].append((0, 1)[min(resdf) > float(c[3])])
                comps[str(frame)].append(min(resdf))
    
            elif c[0] == 'Ratio':
                comps[str(frame)].append((0, 1)[min(resdf)/(sum(resdf)/reslen) >= float(c[3])])
                comps[str(frame)].append(min(resdf)/(sum(resdf)/reslen))
    
            elif c[0] == 'Average':
                comps[str(frame)].append((0, 1)[sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea > float(c[3])])
                comps[str(frame)].append(sum([area * resdf[p] for p, area in enumerate(oareas)])/oarea)
    
        for e in self['ecrit']:
            if e[0] == 'Percent':
                if e[2] == 'DF':
                    edfpass[str(frame)] = [1, (0, 1)[sum(resdf)/reslen > float(e[3])], sum(resdf)/reslen]
                    edfpassarea = edfpassarea + oarea if sum(resdf)/(reslen) > float(e[3]) else edfpassarea
                    ecomps[str(frame)].append((0, 1)[sum(resdf)/reslen > float(e[3])])
                    ecomps[str(frame)].append(sum(resdf)/reslen)
                    edftotarea += oarea
                    
                if e[2] == 'PDF':
                    edfpass[str(frame)] = 1
                    edfpassarea = sum([area for p, area in enumerate(oareas) if resdf[p] > float(e[3])])      
                    ecomps[str(frame)].append((0, 1)[dfpassarea > float(e[1])*oarea/100])
                    ecomps[str(frame)].append(100*edfpassarea/oarea)
                    edftotarea += oarea
    
                elif e[2] == 'Skyview':
                    passarea = sum([area for p, area in enumerate(oareas) if ressv[p] > 0])
                    ecomps[str(frame)].append((0, 1)[passarea >= int(e[1]) * oarea/100])
                    ecomps[str(frame)].append(100*passarea/oarea)
                    passarea = 0
    
            elif e[0] == 'Min':
                ecomps[str(frame)].append((0, 1)[min(resdf) > float(e[3])])
                ecomps[str(frame)].append(min(resdf))
    
            elif e[0] == 'Ratio':
                ecomps[str(frame)].append((0, 1)[min(resdf)/(sum(resdf)/reslen) >= float(e[3])])
                ecomps[str(frame)].append(min(resdf)/(sum(resdf)/reslen))
    
            elif e[0] == 'Average':
                ecomps[str(frame)].append((0, 1)[sum(resdf)/reslen > float(e[3])])
                ecomps[str(frame)].append(sum(resdf)/reslen)
    
            crits.append(self['crit'])
    
        if dfpass[str(frame)] == 1:
            dfpass[str(frame)] = 2 if dfpassarea/dftotarea >= (0.8, 0.35)[simnode['coptions']['canalysis'] == '0' and simnode['coptions']['bambuild'] == '4'] else dfpass[str(frame)]
        if edfpass[str(frame)] == 1:
            edfpass[str(frame)] = 2 if edfpassarea/edftotarea >= (0.8, 0.5)[simnode['coptions']['canalysis'] == '0' and simnode['coptions']['bambuild'] == '4'] else edfpass[str(frame)]
    self['comps'], self['ecomps'] = comps, ecomps

    scene['liparams']['crits'], scene['liparams']['dfpass'] = crits, dfpass
    bm.to_mesh(self.data)
    bm.free()

#def compdisplay(self, scene): 
#    unitdict = {'0': 'df', '1': 'sv'}
#    bm = bmesh.new()
#    bm.from_mesh(self.data)
#    geom = bm.verts if scene['liparams']['cp'] == '1' else bm.faces
#    for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):          
#        livires = geom.layers.float['{}{}'.format(unitdict[scene.li_disp_sv], frame)]
#        res = geom.layers.float['res{}'.format(frame)]
#        oreslist = [g[livires] for g in geom]
#        self['omax'][str(frame)], self['omin'][str(frame)], self['oave'][str(frame)] = max(oreslist), min(oreslist), sum(oreslist)/len(oreslist)
#         
#        try:
#            vals = array([(f[livires] - min(scene['liparams']['minres'].values()))/(max(scene['liparams']['maxres'].values()) - min(scene['liparams']['minres'].values())) for f in bm.faces]) if scene['liparams']['cp'] == '0' else \
#                    ([(sum([vert[livires] for vert in f.verts])/len(f.verts) - min(scene['liparams']['minres'].values()))/(max(scene['liparams']['maxres'].values()) - min(scene['liparams']['minres'].values())) for f in bm.faces])
#        except Exception as e:
#            print(e)
#            vals = array([max(scene['liparams']['maxres'].values()) for g in geom])
#        for g in geom:
#            g[res] = g[livires]   
#        bins = array([0.05*i for i in range(1, 20)])
#        nmatis = digitize(vals, bins)
#        for fi, f in enumerate(bm.faces):
#            if scene.li_disp_sv == '0':
#                f.material_index = nmatis[fi]
#            elif scene.li_disp_sv == '1':
#                f.material_index = 11 if vals[fi] > 0 else 19
#        if scene['liparams']['fe'] - scene['liparams']['fs'] > 0:
#            [self.data.polygons[fi].keyframe_insert('material_index', frame=frame) for fi in range(len(bm.faces))] 
#    bm.to_mesh(self.data)
#    bm.free()
        
def udidacalcapply(self, scene, frames, rccmds, simnode):  
    selobj(scene, self)
    bm = bmesh.new()
    bm.from_mesh(self.data)
    clearlayers(bm)
    geom = bm.verts if self['cpoint'] == '1' else bm.faces
    cindex = geom.layers.int['cindex']
    if self.get('wattres'):
        del self['wattres']
    wattarray = array((0.265, 0.67, 0.065))
    illuarray = 179 * wattarray                              
    vecvals, vals = mtx2vals(open(simnode.inputs['Context in'].links[0].from_socket['Options']['mtxfile'], 'r').readlines(), datetime.datetime(2010, 1, 1).weekday(), '')
    if simnode['coptions']['unit'] in ('DA (%)', 'UDI-a (%)'):
        vecvals = array([vv[2:] for vv in vecvals if simnode['coptions']['cbdm_sh'] <= vv[0] < simnode['coptions']['cbdm_eh'] and vv[1] < simnode['coptions']['weekdays']])
    elif simnode['coptions']['unit'] == 'kW':
        vecvals = array([vv[2:] for vv in vecvals])
    
    for f, frame in enumerate(frames):
        reslen = len(self['rtpoints'][str(frame)].split('\n')) - 1 
            
        if str(frame) in self['rtpoints']:
            rtframe = frame
        else:
            kints = [int(k) for k in self["rtpoints"].keys()]
            rtframe  = max(kints) if frame > max(kints) else  min(kints)
        
        sensarray = zeros((reslen, 146))
        sensrun = Popen(rccmds[f].split(), stdin=PIPE, stdout=PIPE).communicate(input=self['rtpoints'][str(rtframe)].encode('utf-8'))
    
        for li, line in enumerate(sensrun[0].decode("utf-8").splitlines()): 
            reslist = [float(ld) for ld in line.split() if ld not in ('\n', '\r\n')]
            resarray = array(reslist).reshape(146,3)
    
            if simnode['coptions']['unit'] in ('DA (%)', 'UDI-a (%)'):
                sensarray[li] = nsum(resarray*illuarray, axis = 1)
            elif simnode['coptions']['unit'] == 'kW':
                sensarray[li] = nsum(resarray*wattarray, axis = 1)
            
        hours = len(vecvals)
        finalillu = inner(sensarray, vecvals)
        if bpy.context.active_object and bpy.context.active_object.hide == 'False':
            bpy.ops.object.mode_set()              
        bpy.ops.object.select_all(action = 'DESELECT')
        scene.objects.active = None
            
        if simnode['coptions']['unit'] == 'DA (%)':
            res = [nsum([i >= simnode['coptions']['dalux'] for i in f])*100/hours for f in finalillu]
            self['omax']['da{}'.format(frame)] =  max(res)
            self['omin']['da{}'.format(frame)] = min(res)
            self['oave']['da{}'.format(frame)] = sum(res)/len(res)
            geom.layers.float.new('res{}'.format(frame))
            resda = geom.layers.float['res{}'.format(frame)]
            for g in [g for g in geom if g[cindex] > 0]:
                g[resda] = res[g[cindex] - 1]
    
        elif scene['liparams']['unit'] == 'UDI-a (%)':
            res = [[(f<simnode['coptions']['damin']).sum()*100/hours, ((simnode['coptions']['damin']<f)&(f<simnode['coptions']['dasupp'])).sum()*100/hours,
                    ((simnode['coptions']['dasupp']<f)&(f<simnode['coptions']['daauto'])).sum()*100/hours, (simnode['coptions']['daauto']<f).sum()*100/hours] for f in finalillu]
            self['omax']['low{}'.format(frame)] =  max(r[0] for r in res)
            self['omin']['low{}'.format(frame)] = min(r[0] for r in res)
            self['oave']['low{}'.format(frame)] = sum(r[0] for r in res)/len(res)
            self['omax']['sup{}'.format(frame)] =  max(r[1] for r in res)
            self['omin']['sup{}'.format(frame)] = min(r[1] for r in res)
            self['oave']['sup{}'.format(frame)] = sum(r[1] for r in res)/len(res)
            self['omax']['auto{}'.format(frame)] =  max(r[2] for r in res)
            self['omin']['auto{}'.format(frame)] = min(r[2] for r in res)
            self['oave']['auto{}'.format(frame)] = sum(r[2] for r in res)/len(res)
            self['omax']['high{}'.format(frame)] =  max(r[3] for r in res)
            self['omin']['high{}'.format(frame)] = min(r[3] for r in res)
            self['oave']['high{}'.format(frame)] = sum(r[3] for r in res)/len(res)
            udilevels = ('low', 'sup', 'auto', 'high', 'res')
            for udilevel in udilevels:
                geom.layers.float.new('{}{}'.format(udilevel, frame))
            [udilow, udisupp, udiauto, udihigh, udires] = [geom.layers.float['{}{}'.format(udilevel, frame)] for udilevel in udilevels]
            for g in [g for g in geom if g[cindex] > 0]:
                g[udilow] = res[g[cindex] - 1][0]
                g[udisupp] = res[g[cindex] - 1][1]
                g[udiauto] = res[g[cindex] - 1][2]
                g[udihigh] = res[g[cindex] - 1][3]
                g[udires] = res[g[cindex] - 1][int(scene.li_disp_udi)] 
            restext = ''.join(["{} {:.2f} {:.2f} {:.2f}\n".format(self.name, r[0], r[1], r[2], r[3]) for r in res])
            simnode['resdict']['{}-{}-{}'.format(self.name, 'low', frame)] = ['{}-{}-{}'.format(self.name, 'low', frame)] 
            simnode['allresdict']['{}-{}-{}'.format(self.name, 'low', frame)] = [r[0] for r in res]
            simnode['resdict']['{}-{}-{}'.format(self.name, 'supp', frame)] = ['{}-{}-{}'.format(self.name, 'supp', frame)] 
            simnode['allresdict']['{}-{}-{}'.format(self.name, 'supp', frame)] = [r[1] for r in res]
            simnode['resdict']['{}-{}-{}'.format(self.name, 'auto', frame)] = ['{}-{}-{}'.format(self.name, 'auto', frame)] 
            simnode['allresdict']['{}-{}-{}'.format(self.name, 'auto', frame)] = [r[2] for r in res]
            simnode['resdict']['{}-{}-{}'.format(self.name, 'high', frame)] = ['{}-{}-{}'.format(self.name, 'high', frame)] 
            simnode['allresdict']['{}-{}-{}'.format(self.name, 'high', frame)] = [r[3] for r in res]
            simnode['resdict']['{}-{}-{}'.format(self.name, 'lux', frame)] = ['{}-{}-{}'.format(self.name, 'lux', frame)] 
            simnode['allresdict']['{}-{}-{}'.format(self.name, 'lux', frame)] = [f for f in finalillu]
            
    bm.to_mesh(self.data)
    bm.free()
    
def retvpvloc(context):
    view_mat = context.space_data.region_3d.perspective_matrix
    view_pivot = context.region_data.view_location

    if context.space_data.region_3d.is_perspective:
        vw = mathutils.Vector((-view_mat[3][0], -view_mat[3][1], -view_mat[3][2])).normalized()
        view_location = view_pivot + (vw * bpy.context.region_data.view_distance)    
    else:
        vw =  mathutils.Vector((0.0, 0.0, 1.0))
        vw.rotate(bpy.context.region_data.view_rotation)
        view_location = view_pivot + vw.normalized()*bpy.context.region_data.view_distance * 100 
    return (view_location, view_mat, vw)
          
def fvmat(self, mn, bound):
#    fvname = on.replace(" ", "_") + self.name.replace(" ", "_") 
    begin = '\n  {}\n  {{\n    type    '.format(mn)  
    end = ';\n  }\n'
    
    if bound == 'p':
        val = 'uniform {}'.format(self.flovi_b_sval) if not self.flovi_p_field else '$internalField'
        pdict = {'0': self.flovi_bmwp_type, '1': self.flovi_bmip_type, '2': self.flovi_bmop_type, '3': 'symmetryPlane', '4': 'empty'}
        ptdict = {'zeroGradient': 'zeroGradient', 'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'calculated': 'calculated;\n    value    $internalField', 
        'freestreamPressure': 'freestreamPressure', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
#        if pdict[self.flovi_bmb_type] == 'zeroGradient':
        entry = ptdict[pdict[self.flovi_bmb_type]]            
#        return begin + entry + end 
    
    elif bound == 'U':
        val = 'uniform ({} {} {})'.format(*self.flovi_b_vval) if not self.flovi_u_field else '$internalField'
        Udict = {'0': self.flovi_bmwu_type, '1': self.flovi_bmiu_type, '2': self.flovi_bmou_type, '3': 'symmetryPlane', '4': 'empty'}
        Utdict = {'fixedValue': 'fixedValue;\n    value    {}'.format(val), 'slip': 'slip', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
                  'pressureInletOutletVelocity': 'pressureInletOutletVelocity;\n    value    $internalField', 'zeroGradient': 'zeroGradient', 'symmetryPlane': 'symmetryPlane', 
                  'freestream': 'freestream;\n    freestreamValue    $internalField','calculated': 'calculated;\n    value    $internalField', 'empty': 'empty'}
        entry = Utdict[Udict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nut':
        ndict = {'0': self.flovi_bmwnut_type, '1': self.flovi_bminut_type, '2': self.flovi_bmonut_type, '3': 'symmetryPlane', '4': 'empty'}
        ntdict = {'nutkWallFunction': 'nutkWallFunction;\n    value    $internalField', 'nutUSpaldingWallFunction': 'nutUSpaldingWallFunction;\n    value    $internalField', 
        'calculated': 'calculated;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',  'symmetryPlane': 'symmetryPlane','empty': 'empty'}
        entry = ntdict[ndict[self.flovi_bmb_type]]            
#        return begin + entry + end

    elif bound == 'k':
        kdict = {'0': self.flovi_bmwk_type, '1': self.flovi_bmik_type, '2': self.flovi_bmok_type, '3': 'symmetryPlane', '4': 'empty'}
        ktdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'kqRWallFunction': 'kqRWallFunction;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField',
        'calculated': 'calculated;\n    value    $internalField', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
        entry = ktdict[kdict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'e':
        edict = {'0': self.flovi_bmwe_type, '1': self.flovi_bmie_type, '2': self.flovi_bmoe_type, '3': 'symmetryPlane', '4': 'empty'}
        etdict = {'symmetryPlane': 'symmetryPlane', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField', 
                  'epsilonWallFunction': 'epsilonWallFunction;\n    value    $internalField', 'calculated': 'calculated;\n    value    $internalField', 'symmetryPlane': 'symmetryPlane', 'empty': 'empty'}
        entry = etdict[edict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'o':
        odict = {'0': self.flovi_bmwo_type, '1': self.flovi_bmio_type, '2': self.flovi_bmoo_type, '3': 'symmetryPlane', '4': 'empty'}
        otdict = {'symmetryPlane': 'symmetryPlane', 'empty': 'empty', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'zeroGradient': 'zeroGradient', 
                  'omegaWallFunction': 'omegaWallFunction;\n    value    $internalField', 'fixedValue': 'fixedValue;\n    value    $internalField'}
        entry = otdict[odict[self.flovi_bmb_type]]            
#        return begin + entry + end
        
    elif bound == 'nutilda':
        ntdict = {'0': self.flovi_bmwnutilda_type, '1': self.flovi_bminutilda_type, '2': self.flovi_bmonutilda_type, '3': 'symmetryPlane', '4': 'empty'}
        nttdict = {'fixedValue': 'fixedValue;\n    value    $internalField', 'inletOutlet': 'inletOutlet;\n    inletValue    $internalField\n    value    $internalField', 'empty': 'empty', 
                   'zeroGradient': 'zeroGradient', 'freestream': 'freestream\n    freeStreamValue  $internalField\n', 'symmetryPlane': 'symmetryPlane'} 
        entry = nttdict[ntdict[self.flovi_bmb_type]]            
    return begin + entry + end
        
def recalculate_text(scene):   
    resdict = {'Temp': ('envi_temp', u'\u00b0C'), 'Hum': ('envi_hum', '%'), 'CO2': ('envi_co2', 'ppm'), 'Heat': ('envi_heat', 'hW'), 'Cool': ('envi_cool', 'cW')}
    for res in resdict:    
        for o in [o for o in bpy.data.objects if o.get('VIType') and o['VIType'] == resdict[res][0] and o.children]:
            txt = o.children[0] 
            sf = scene.frame_current if scene.frame_current <= scene.frame_end else scene.frame_end
            txt.data.body = ("{:.1f}", "{:.0f}")[res in ('Heat', 'CO2')].format(o['envires'][res][sf]) + resdict[res][1]
        
def envilres(scene, resnode):
    for rd in resnode['resdict']:
        if resnode['resdict'][rd][0][:4] == 'WIN-':
            baseob = [o for o in bpy.data.objects if o.name.upper() == resnode['resdict'][rd][0][7:][:-2]][0]
            basefacecent = baseob.matrix_world * baseob.data.polygons[int(resnode['resdict'][rd][0][4:].split('_')[-1])].center
            if scene.envi_flink:
                posobs = [o for o in bpy.data.objects if o.vi_type == '0' and o.layers[0]]
                dists = [(o.location - basefacecent).length for o in posobs]
                resob = posobs[dists.index(min(dists))]
                if not resob.get('envires'):
                    resob['envires'] = {}
            else:
                resob = baseob
            
            if resob.data.shape_keys and resnode['resdict'][rd][1] == 'Opening Factor':
                resob['envires']['LOF'] = resnode['allresdict'][rd]
                for frame in range(scene.frame_start, scene.frame_end + 1):
                    scene.frame_set(frame) 
                    resob.data.shape_keys.key_blocks[1].value = resob['envires']['LOF'][frame]
                    resob.data.shape_keys.key_blocks[1].keyframe_insert(data_path = 'value', frame = frame)
            
            if resob.data.shape_keys and resnode['resdict'][rd][1] == 'Linkage Flow in':
                bpy.ops.mesh.primitive_cone_add()
                fcone = bpy.context.active_object
                fcone.rotation_euler = resob.rotation_euler if scene.envi_flink else mathutils.angle(fcone.matrix_world * fcone.data.polygons[-1].normal, resob.matrix_word * resob.data.polygons[int(resnode['resdict'][rd][0].split('_')[-1])].normal)
                fcone.parent = resob
                fcone['envires'] = {}
                fi = resnode['allresdict'][rd]
                
                for frd in resnode['resdict']:
                    if resnode['resdict'][frd][0] == resnode['resdict'][rd][0] and resnode['resdict'][frd][1] == 'Linkage Flow out':
                        fo = resnode['allresdict'][frd]
                fcone['envires']['flow'] = [float(fival) - float(foval) for fival, foval in zip(fi,fo)]
                
                for frame in range(scene.frame_start, scene.frame_end + 1):
                    scene.frame_set(frame)
                    fcone.rotation_euler = fcone.rotation_euler.to_matrix().inverted().to_euler()
                    fcone.scale = [10*float(fcone['envires']['flow'][frame]) for i in range(3)]
                    fcone.keyframe_insert(data_path = 'scale', frame = frame)
                    fcone.keyframe_insert(data_path = 'rotation_euler', frame = frame)

def envizres(scene, eresobs, resnode, restype):
    resdict = {'Temp': ('Temperature (degC)', scene.en_temp_max, scene.en_temp_min, u"\u00b0C"), 'Hum': ('Humidity (%)', scene.en_hum_max, scene.en_hum_min, '%'),
               'CO2': ('CO2 (ppm)', scene.en_co2_max, scene.en_co2_min, 'ppm'), 'Heat': ('Heating (W)', scene.en_heat_max, scene.en_heat_min, 'W')}
    rl = resnode['reslists']
    zrl = list(zip(*rl))
    resstart = 24 * (resnode['Start'] - resnode.dsdoy)
    resend = resstart + 24 * (1 + resnode['End'] - resnode['Start'])
    maxval = max([[max(float(r) for r in zrl[4][ri].split())][0] for ri, r in enumerate(zrl[3]) if r == resdict[restype][0]and zrl[1][ri] == 'Zone']) 
    minval = min([[min(float(r) for r in zrl[4][ri].split())][0] for ri, r in enumerate(zrl[3]) if r == resdict[restype][0]and zrl[1][ri] == 'Zone'])

    for eo in eresobs:
        o = bpy.data.objects[eo[3:]]
        valstring = [r[4].split()[resstart:resend] for r in rl if r[2] == eo.upper() and r[3] == resdict[restype][0]]
        vals = [float(v) for v in valstring[0]]
        opos = o.matrix_world * mathutils.Vector([sum(ops)/8 for ops in zip(*o.bound_box)])
    
        if not o.children or not any([restype in oc['envires'] for oc in o.children if oc.get('envires')]):
            if scene.en_disp == '1':
                bpy.ops.mesh.primitive_plane_add()  
            elif scene.en_disp == '0':
                bpy.ops.mesh.primitive_circle_add(fill_type = 'NGON')   
            ores = bpy.context.active_object
            ores['VIType'] = 'envi_{}'.format(restype.lower())
            if not ores.get('envires'):
                ores['envires'] = {}
            ores['envires'][restype] = vals
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.extrude_region_move(MESH_OT_extrude_region={"mirror":False}, TRANSFORM_OT_translate={"value":(0, 0, 1), "constraint_axis":(False, False, True), "constraint_orientation":'NORMAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "gpencil_strokes":False, "texture_space":False, "remove_on_cancel":False, "release_confirm":False})
            bpy.ops.object.editmode_toggle()
            ores.scale, ores.parent = (0.25, 0.25, 0.25), o
            ores.location = o.matrix_world.inverted() * opos
            bpy.ops.object.material_slot_add()
            mat = bpy.data.materials.new(name = '{}_{}'.format(o.name, restype.lower()))
            ores.material_slots[0].material = mat 
            bpy.ops.object.text_add(radius=1, view_align=False, enter_editmode=False, layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
            txt = bpy.context.active_object
            bpy.context.object.data.extrude = 0.005
            bpy.ops.object.material_slot_add()
            txt.parent = ores
            txt.location, txt.scale = (0,0,0), (ores.scale[0]*2, ores.scale[1]*2, 1)
            txt.data.align = 'CENTER'
            txt.name = '{}_{}_text'.format(o.name, restype)
            txt.data.body = "{:.1f}{}".format(ores['envires'][restype][0], resdict[restype][3]) if restype !='CO2' else "{:.0f}{}".format(ores['envires'][restype][0], resdict[restype][2])
            tmat = bpy.data.materials.new(name = '{}'.format(txt.name))
            tmat.diffuse_color = (0, 0, 0)
            txt.material_slots[0].material = tmat
        else:
            ores = [o for o in o.children if o.get('envires') and restype in o['envires']][0] 
            ores['envires'][restype] = vals
            mat = ores.material_slots[0].material
            if not ores.children:
                bpy.ops.object.text_add(radius=1, view_align=False, enter_editmode=False, layers=(True, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False))
                txt = bpy.context.active_object
                bpy.context.object.data.extrude = 0.005
                bpy.ops.object.material_slot_add()
                txt.parent = ores
                txt.location, txt.scale = (0,0,0), (ores.scale[0], ores.scale[1], 1)
                txt.data.align = 'CENTER'
                txt.name = '{}_{}_text'.format(o.name, restype)
                tmat = bpy.data.materials.new(name = '{}'.format(txt.name))
                tmat.diffuse_color = (0, 0, 0)
                txt.material_slots[0].material = tmat
            else:
                txt = ores.children[0]
            txt.data.body = u"{:.1f}\u00b0C".format(ores['envires'][restype][0]) 

        scaleval =  [(vals[frame] - minval)/(maxval - minval) for frame in range(0, len(vals))]
        sv = [(sv, 0.1)[sv <= 0.1] for sv in scaleval]
        colval = [colorsys.hsv_to_rgb(0.667 * (maxval - vals[vi])/(maxval - minval), 1, 1) for vi in range(len(vals))]
        cv = [(((0, 1)[vals[c] >= maxval], 0, (0, 1)[vals[c] <= minval]), cv)[minval < vals[c] < maxval] for c, cv in enumerate(colval)]
    
        ores.animation_data_clear()
        ores.animation_data_create()
        ores.animation_data.action = bpy.data.actions.new(name="EnVi Zone")
        oresz = ores.animation_data.action.fcurves.new(data_path="scale", index = 2)
        oresz.keyframe_points.add(len(sv))
        mat.animation_data_clear()
        mat.animation_data_create()
        mat.animation_data.action = bpy.data.actions.new(name="EnVi Zone Material")
        mdcr = mat.animation_data.action.fcurves.new(data_path="diffuse_color", index = 0)
        mdcg = mat.animation_data.action.fcurves.new(data_path="diffuse_color", index = 1)
        mdcb = mat.animation_data.action.fcurves.new(data_path="diffuse_color", index = 2)
        mdcr.keyframe_points.add(len(sv))
        mdcg.keyframe_points.add(len(sv))
        mdcb.keyframe_points.add(len(sv))
        txt.animation_data_clear()
        txt.animation_data_create()
        txt.animation_data.action = bpy.data.actions.new(name="EnVi Zone Text")
        txtl = txt.animation_data.action.fcurves.new(data_path="location", index = 2)
        txtl.keyframe_points.add(len(sv))

        for frame in range(len(sv)):
            oresz.keyframe_points[frame].co = frame, sv[frame]
            mdcr.keyframe_points[frame].co = frame, cv[frame][0]
            mdcg.keyframe_points[frame].co = frame, cv[frame][1]
            mdcb.keyframe_points[frame].co = frame, cv[frame][2]
            txtl.keyframe_points[frame].co = frame, 1
            
def radpoints(o, faces, sks):
    fentries = ['']*len(faces)   
    if sks:
        (skv0, skv1, skl0, skl1) = sks
    for f, face in enumerate(faces):
        fmat = o.data.materials[face.material_index]
        mname = '{}_{}_{}'.format(fmat.name.replace(" ", "_"), o.name.replace(" ", "_"), face.index) if fmat.radmatmenu == '8' else fmat.name.replace(" ", "_")
        fentry = "# Polygon \n{} polygon poly_{}_{}\n0\n0\n{}\n".format(mname, o.name.replace(" ", "_"), face.index, 3*len(face.verts))
        if sks:
            ventries = ''.join([" {0[0]} {0[1]} {0[2]}\n".format((o.matrix_world*mathutils.Vector((v[skl0][0]+(v[skl1][0]-v[skl0][0])*skv1, v[skl0][1]+(v[skl1][1]-v[skl0][1])*skv1, v[skl0][2]+(v[skl1][2]-v[skl0][2])*skv1)))) for v in face.verts])
        else:
            ventries = ''.join([" {0[0]:.3f} {0[1]:.3f} {0[2]:.3f}\n".format(v.co) for v in face.verts])
        fentries[f] = ''.join((fentry, ventries+'\n'))        
    return ''.join(fentries)
                       
def viparams(op, scene):
    if not bpy.data.filepath:
#        op.report({'ERROR'},"The Blender file has not been saved. Save the Blender file before exporting")
        return 'Save file'
    if " "  in bpy.data.filepath:
        op.report({'ERROR'},"The directory path or Blender filename has a space in it. Please save again without any spaces in the file name or the directory path")
        return 'Rename file'
    fd, fn = os.path.dirname(bpy.data.filepath), os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not os.path.isdir(os.path.join(fd, fn)):
        os.makedirs(os.path.join(fd, fn))
    if not os.path.isdir(os.path.join(fd, fn, 'obj')):
        os.makedirs(os.path.join(fd, fn, 'obj'))
    if not os.path.isdir(os.path.join(fd, fn, 'bsdfs')):
        os.makedirs(os.path.join(fd, fn, 'bsdfs'))
    if not os.path.isdir(os.path.join(fd, fn, 'lights')):
        os.makedirs(os.path.join(fd, fn, 'lights'))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam'))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'system')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "system"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant', 'polyMesh')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant", "polyMesh"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', 'constant', 'triSurface')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "constant", "triSurface"))
    if not os.path.isdir(os.path.join(fd, fn, 'Openfoam', '0')):
        os.makedirs(os.path.join(fd, fn, 'Openfoam', "0"))
        
    nd = os.path.join(fd, fn)
    fb, ofb, lfb, offb, idf  = os.path.join(nd, fn), os.path.join(nd, 'obj'), os.path.join(nd, 'lights'), os.path.join(nd, 'Openfoam'), os.path.join(nd, 'in.idf')
    offzero, offs, offc, offcp, offcts = os.path.join(offb, '0'), os.path.join(offb, 'system'), os.path.join(offb, 'constant'), os.path.join(offb, 'constant', "polyMesh"), os.path.join(offb, 'constant', "triSurface")
    if not scene.get('viparams'):
        scene['viparams'] = {}
    scene['viparams']['cat'] = ('cat ', 'type ')[str(sys.platform) == 'win32']
    scene['viparams']['nproc'] = str(multiprocessing.cpu_count())
    scene['viparams']['wnproc'] = str(multiprocessing.cpu_count()) if str(sys.platform) != 'win32' else '1'
    scene['viparams']['filepath'] = bpy.data.filepath
    scene['viparams']['filename'] = fn
    scene['viparams']['filedir'] = fd
    scene['viparams']['newdir'] = nd 
    scene['viparams']['filebase'] = fb
    if not scene.get('liparams'):
        scene['liparams'] = {}
    scene['liparams']['objfilebase'] = ofb
    scene['liparams']['lightfilebase'] = lfb
    scene['liparams']['disp_count'] = 0
    if not scene.get('enparams'):
        scene['enparams'] = {}
    scene['enparams']['idf_file'] = idf
    scene['enparams']['epversion'] = '8.4'
    if not scene.get('flparams'):
        scene['flparams'] = {}
    scene['flparams']['offilebase'] = offb
    scene['flparams']['ofsfilebase'] = offs
    scene['flparams']['ofcfilebase'] = offc
    scene['flparams']['ofcpfilebase'] = offcp
    scene['flparams']['of0filebase'] = offzero
    scene['flparams']['ofctsfilebase'] = offcts

def resnameunits():
    rnu = {'0': ("Air", "Ambient air metrics"),'1': ("Wind Speed", "Ambient Wind Speed (m/s)"), '2': ("Wind Direction", "Ambient Wind Direction (degrees from North)"),
                '3': ("Humidity", "Ambient Humidity"),'4': ("Solar", 'Ambient solar metrics'), '5': ("Temperature", "Zone Temperature"), '6': ("Humidity", "Zone Humidity"),
                '7': ("Heating Watts", "Zone Heating Requirement (Watts)"), '8': ("Cooling Watts", "Zone Cooling Requirement (Watts)"),
                '9': ("Solar Gain", "Window Solar Gain (Watts)"), '10': ("PPD", "Percentage Proportion Dissatisfied"), '11': ("PMV", "Predicted Mean Vote"),
                '12': ("Ventilation (l/s)", "Zone Ventilation rate (l/s)"), '13': (u'Ventilation (m\u00b3/h)', u'Zone Ventilation rate (m\u00b3/h)'),
                '14': (u'Infiltration (m\u00b3)',  u'Zone Infiltration (m\u00b3)'), '15': ('Infiltration (ACH)', 'Zone Infiltration rate (ACH)'), '16': ('CO2 (ppm)', 'Zone CO2 concentration (ppm)'),
                '17': ("Heat loss (W)", "Ventilation Heat Loss (W)"), '18': (u'Flow (m\u00b3/s)', u'Linkage flow (m\u00b3/s)'), '19': ('Opening factor', 'Linkage Opening Factor'),
                '20': ("MRT (K)", "Mean Radiant Temperature (K)"), '21': ('Occupancy', 'Occupancy count'), '22': ("Humidity", "Zone Humidity"),
                '23': ("Fabric HB (W)", "Fabric convective heat balance"), '24': ("Air Heating", "Zone air heating"), '25': ("Air Cooling", "Zone air cooling"), '26': ("HR Heating", "Heat recovery heating (W)")}
    return [bpy.props.BoolProperty(name = rnu[str(rnum)][0], description = rnu[str(rnum)][1], default = False) for rnum in range(len(rnu))]

def aresnameunits():
    rnu = {'0': (u"Max temp (\u2103)", "Maximum zone temperature"), '1': (u"Min temp (\u2103)", "Minimum zone temperature"), '2': (u"Ave temp (\u2103)", "Average zone temperature"), 
                '3': ("Heating (kWh)", "Zone heating"), '4': (u"Heating (kWh/m\u00b2)", "Zone heating per floor area"), '5': ("Cooling (kWh)", "Zone cooling"), '6': (u"Cooling (kWh/m\u00b2)", "Zone cooling per floor area"), 
                '7': (u"Max CO\u2082 (ppm)", u"Maximum zone CO\u2082 level"), '8': (u"Ave CO\u2082 (ppm)", u"Average zone CO\u2082 level"), '9': (u"Min CO\u2082 (ppm)", u"Minimum zone CO\u2082 level"),
                '10': (u"Max flow in (m\u00b3/s)", u"Maximum linkage flow level"), '11': (u"Min flow in (m\u00b3/s)", u"Minimum linkage flow level"), '12': (u"Ave flow in (m\u00b3/s)", u"Average linkage flow level")}
    return [bpy.props.BoolProperty(name = rnu[str(rnum)][0], description = rnu[str(rnum)][1], default = False) for rnum in range(len(rnu))]

def enresprops(disp):
    return {'0': (0, "restt{}".format(disp), "resh{}".format(disp), 0, "restwh{}".format(disp), "restwc{}".format(disp), 0, 
                  "ressah{}".format(disp), "reshrhw{}".format(disp), 0, "ressac{}".format(disp), "reswsg{}".format(disp), 0, "resfhb{}".format(disp)),
            '1': (0, "rescpp{}".format(disp), "rescpm{}".format(disp), 0, 'resmrt{}'.format(disp), 'resocc{}'.format(disp)), 
            '2': (0, "resim{}".format(disp), "resiach{}".format(disp), 0, "resco2{}".format(disp), "resihl{}".format(disp)), 
            '3': (0, "resl12ms{}".format(disp), "reslof{}".format(disp))}
        
def nodestate(self, opstate):
    if self['exportstate'] !=  opstate:
        self.exported = False
        if self.bl_label[0] != '*':
            self.bl_label = '*'+self.bl_label
    else:
        self.exported = True
        if self.bl_label[0] == '*':
            self.bl_label = self.bl_label[1:-1]

def face_centre(ob, obresnum, f):
    if obresnum:
        vsum = mathutils.Vector((0, 0, 0))
        for v in f.vertices:
            vsum = ob.active_shape_key.data[v].co + vsum
        return(vsum/len(f.vertices))
    else:
        return(f.center)

def v_pos(ob, v):
    return(ob.active_shape_key.data[v].co if ob.lires else ob.data.vertices[v].co)
    
def newrow(layout, s1, root, s2):
    row = layout.row()
    row.label(s1)
    row.prop(root, s2)

def retobj(name, fr, node, scene):
    if node.animmenu == "Geometry":
        return(os.path.join(scene['liparams']['objfilebase'], "{}-{}.obj".format(name.replace(" ", "_"), fr)))
    else:
        return(os.path.join(scene['liparams']['objfilebase'], "{}-{}.obj".format(name.replace(" ", "_"), bpy.context.scene.frame_start)))

def retelaarea(node):
    inlinks = [sock.links[0] for sock in node.inputs if sock.bl_idname in ('EnViSSFlowSocket', 'EnViSFlowSocket') and sock.links]
    outlinks = [sock.links[:] for sock in node.outputs if sock.bl_idname in ('EnViSSFlowSocket', 'EnViSFlowSocket') and sock.links]
    inosocks = [link.from_socket for link in inlinks if inlinks and link.from_socket.node.get('zone')]
    outosocks = [link.to_socket for x in outlinks for link in x if link.to_socket.node.get('zone')]
    if outosocks or inosocks:
        elaarea = max([facearea(bpy.data.objects[sock.node.zone], bpy.data.objects[sock.node.zone].data.polygons[int(sock.sn)]) for sock in outosocks + inosocks])
        node["_RNA_UI"] = {"ela": {"max":elaarea}}
        
def objmode():
    if bpy.context.active_object and bpy.context.active_object.type == 'MESH' and not bpy.context.active_object.hide:
        bpy.ops.object.mode_set(mode = 'OBJECT')

def objoin(obs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select = True
    bpy.context.scene.objects.active = obs[-1]
    bpy.ops.object.join()
    return bpy.context.active_object
    
def retmesh(name, fr, node, scene):
    if node.animmenu in ("Geometry", "Material"):
        return(os.path.join(scene['liparams']['objfilebase'], '{}-{}.mesh'.format(name.replace(" ", "_"), fr)))
    else:
        return(os.path.join(scene['liparams']['objfilebase'], '{}-{}.mesh'.format(name.replace(" ", "_"), bpy.context.scene.frame_start)))

def nodeinputs(node):
    try:
        ins = [i for i in node.inputs if not i.hide]
        if ins and not all([i.links for i in ins]):
            return 0
        elif ins and any([i.links[0].from_node.use_custom_color for i in ins if i.links]):
            return 0
        else:
            inodes = [i.links[0].from_node for i in ins if i.links[0].from_node.inputs]
            for inode in inodes:
                iins = [i for i in inode.inputs if not i.hide]
                if iins and not all([i.is_linked for i in iins]):
                    return 0
                elif iins and not all([i.links[0].from_node.use_custom_color for i in iins if i.is_linked]):
                    return 0
        return 1
    except:
        pass

def retmat(fr, node, scene):
    if node.animmenu == "Material":
        return("{}-{}.rad".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.rad".format(scene['viparams']['filebase'], scene.frame_start))

def retsky(fr, node, scene):
    if node.animmenu == "Time":
        return("{}-{}.sky".format(scene['viparams']['filebase'], fr))
    else:
        return("{}-{}.sky".format(scene['viparams']['filebase'], scene.frame_start))

def nodeexported(self):
    self.exported = 0

def negneg(x):
    x = 0 if float(x) < 0 else x        
    return float(x)

def clearanim(scene, obs):
    for o in obs:
        selobj(scene, o)
        o.animation_data_clear()
        o.data.animation_data_clear()        
        while o.data.shape_keys:
            bpy.context.object.active_shape_key_index = 0
            bpy.ops.object.shape_key_remove(all=True)
            
def clearfiles(filebase):
    fileList = os.listdir(filebase)
    for fileName in fileList:
        os.remove(os.path.join(filebase, fileName))
                    
def clearscene(scene, op):
    for ob in [ob for ob in scene.objects if ob.type == 'MESH' and ob.layers[scene.active_layer]]:
        if ob.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode = 'OBJECT')
        if ob.get('lires'):
            scene.objects.unlink(ob)       
        if scene.get('livig') and ob.name in scene['livig']:
            v, f, svv, svf = [0] * 4             
            if 'export' in op.name or 'simulation' in op.name:
                bm = bmesh.new()
                bm.from_mesh(ob.data)
                if "export" in op.name:
                    if bm.faces.layers.int.get('rtindex'):
                        bm.faces.layers.int.remove(bm.faces.layers.int['rtindex'])
                    if bm.verts.layers.int.get('rtindex'):
                        bm.verts.layers.int.remove(bm.verts.layers.int['rtindex'])
                if "simulation" in op.name:
                    while bm.verts.layers.float.get('res{}'.format(v)):
                        livires = bm.verts.layers.float['res{}'.format(v)]
                        bm.verts.layers.float.remove(livires)
                        v += 1
                    while bm.faces.layers.float.get('res{}'.format(f)):
                        livires = bm.faces.layers.float['res{}'.format(f)]
                        bm.faces.layers.float.remove(livires)
                        f += 1
                bm.to_mesh(ob.data)
                bm.free()

    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for lamp in bpy.data.lamps:
        if lamp.users == 0:
            bpy.data.lamps.remove(lamp)

    for oldgeo in bpy.data.objects:
        if oldgeo.users == 0:
            bpy.data.objects.remove(oldgeo)

    for sk in bpy.data.shape_keys:
        if sk.users == 0:
            for keys in sk.keys():
                keys.animation_data_clear()

def retmenu(dnode, axis, mtype):
    if mtype == 'Climate':
        return ['', dnode.inputs[axis].climmenu]
    if mtype == 'Zone':
        return [dnode.inputs[axis].zonemenu, dnode.inputs[axis].zonermenu]
    elif mtype == 'Linkage':
        return [dnode.inputs[axis].linkmenu, dnode.inputs[axis].linkrmenu]
    elif mtype == 'External node':
        return [dnode.inputs[axis].enmenu, dnode.inputs[axis].enrmenu]
    elif mtype == 'Frames':
        return ['', 'Frames']
        
def retdata(dnode, axis, mtype, resdict, frame):
    if mtype == 'Climate':
        return resdict[frame][mtype][dnode.inputs[axis].climmenu]
    if mtype == 'Zone':
        return resdict[frame][mtype][dnode.inputs[axis].zonemenu][dnode.inputs[axis].zonermenu]
    elif mtype == 'Linkage':
        return resdict[frame][mtype][dnode.inputs[axis].linkmenu][dnode.inputs[axis].linkrmenu]
    elif mtype == 'External node':
        return resdict[frame][mtype][dnode.inputs[axis].enmenu][dnode.inputs[axis].enrmenu]

def retrmenus(innode, node): 
    rl = innode['reslists']
    zrl = list(zip(*rl))
    ftype = [(frame, frame, "Plot "+frame) for frame in list(OrderedDict.fromkeys(zrl[0])) if frame != 'All']        
    frame = 'All' if node.animated and len(ftype) > 1 else zrl[0][0]
    rtypes = list(OrderedDict.fromkeys([zrl[1][ri] for ri, r in enumerate(zrl[1]) if zrl[0][ri] == frame]))
    rtype = [(metric, metric, "Plot " + metric) for metric in rtypes]
    ctype = [(metric, metric, "Plot " + metric) for m, metric in enumerate(zrl[3]) if zrl[1][m] == 'Climate' and zrl[0][m] == frame]
    ztypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[2]) if zrl[1][m] == 'Zone' and zrl[0][m] == frame]))
    ztype = [(metric, metric, "Plot " + metric) for metric in ztypes]
    zrtypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[3]) if zrl[1][m] == 'Zone' and zrl[0][m] == frame]))
    zrtype = [(metric, metric, "Plot " + metric) for metric in zrtypes]
    ltypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[2]) if zrl[1][m] == 'Linkage' and zrl[0][m] == frame]))
    ltype = [(metric, metric, "Plot " + metric) for metric in ltypes]
    lrtypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[3]) if zrl[1][m] == 'Linkage' and zrl[0][m] == frame]))
    lrtype = [(metric, metric, "Plot " + metric) for metric in lrtypes]
    entypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[2]) if zrl[1][m] == 'External' and zrl[0][m] == frame]))
    entype = [(metric, metric, "Plot " + metric) for metric in entypes]
    enrtypes = list(OrderedDict.fromkeys([metric for m, metric in enumerate(zrl[3]) if zrl[1][m] == 'External' and zrl[0][m] == frame]))       
    enrtype = [(metric, metric, "Plot " + metric) for metric in enrtypes]    

    fmenu = bpy.props.EnumProperty(items=ftype, name="", description="Frame number", default = ftype[0][0])
    rtypemenu = bpy.props.EnumProperty(items=rtype, name="", description="Result types", default = rtype[0][0])
    statmenu = bpy.props.EnumProperty(items=[('Average', 'Average', 'Average Value'), ('Maximum', 'Maximum', 'Maximum Value'), ('Minimum', 'Minimum', 'Minimum Value')], name="", description="Zone result", default = 'Average')
    valid = ['Vi Results']    
    climmenu = bpy.props.EnumProperty(items=ctype, name="", description="Climate type", default = ctype[0][0]) if ctype else ''     
    zonemenu = bpy.props.EnumProperty(items=ztype, name="", description="Zone", default = ztype[0][0]) if ztype else ''
    zonermenu = bpy.props.EnumProperty(items=zrtype, name="", description="Zone result", default = zrtype[0][0])  if ztype else ''
    linkmenu = bpy.props.EnumProperty(items=ltype, name="", description="Flow linkage result", default = ltype[0][0]) if ltype else ''
    linkrmenu = bpy.props.EnumProperty(items=lrtype, name="", description="Flow linkage result", default = lrtype[0][0]) if ltype else ''
    enmenu = bpy.props.EnumProperty(items=entype, name="", description="External node result", default = entype[0][0]) if entype else ''
    enrmenu = bpy.props.EnumProperty(items=enrtype, name="", description="External node result", default = enrtype[0][0]) if entype else ''
    multfactor = bpy.props.FloatProperty(name = "", description = "Result multiplication factor", min = 0.0001, max = 10000, default = 1)
    
    return (valid, fmenu, statmenu, rtypemenu, climmenu, zonemenu, zonermenu, linkmenu, linkrmenu, enmenu, enrmenu, multfactor)

def processh(lines):
    envdict = {'Site Outdoor Air Drybulb Temperature [C] !Hourly': "Temperature (degC)",
               'Site Outdoor Air Relative Humidity [%] !Hourly': 'Humidity (%)',
                'Site Wind Direction [deg] !Hourly': 'Wind Direction (deg)',
                'Site Wind Speed [m/s] !Hourly': 'Wind Speed (m/s)',
                'Site Diffuse Solar Radiation Rate per Area [W/m2] !Hourly': "Diffuse Solar (W/m^2)",
                'Site Direct Solar Radiation Rate per Area [W/m2] !Hourly': "Direct Solar (W/m^2)"}
    zresdict = {'Zone Air Temperature [C] !Hourly': "Temperature (degC)",
                'Zone Air Relative Humidity [%] !Hourly': 'Humidity (%)',
                'Zone Air System Sensible Heating Rate [W] !Hourly': 'Heating (W)',
                'Zone Air System Sensible Cooling Rate [W] !Hourly': 'Cooling (W)',
                'Zone Ideal Loads Supply Air Sensible Heating Rate [W] !Hourly': 'Zone air heating (W)',
                'Zone Ideal Loads Heat Recovery Sensible Heating Rate [W] !Hourly': 'Zone HR heating (W)',
                'Zone Ideal Loads Supply Air Sensible Cooling Rate [W] !Hourly': 'Zone air cooling (W)',
                'Zone Windows Total Transmitted Solar Radiation Rate [W] !Hourly': 'Solar gain (W)',
                'Zone Infiltration Current Density Volume Flow Rate [m3/s] !Hourly': 'Infiltration (m'+u'\u00b3'+')',
                'Zone Infiltration Air Change Rate [ach] !Hourly': 'Infiltration (ACH)',
                'Zone Mean Air Temperature [C] ! Hourly': 'Mean Temperature ({})'.format(u'\u00b0'),
                'Zone Mean Radiant Temperature [C] !Hourly' :'Mean Radiant ({})'.format(u'\u00b0'), 
                'Zone Thermal Comfort Fanger Model PPD [%] !Hourly' :'PPD',
                'Zone Thermal Comfort Fanger Model PMV [] !Hourly' :'PMV',               
                'AFN Node CO2 Concentration [ppm] !Hourly': 'CO2 (ppm)',
                'Zone Air CO2 Concentration [ppm] !Hourly': 'CO2 (ppm)',
                'Zone Mean Radiant Temperature [C] !Hourly': 'MRT', 
                'Zone People Occupant Count [] !Hourly': 'Occupancy', 
                'Zone Air Heat Balance Surface Convection Rate [W] !Hourly': 'Heat balance (W)'}
    enresdict = {'AFN Node CO2 Concentration [ppm] !Hourly': 'CO2'}
    lresdict = {'AFN Linkage Node 1 to Node 2 Volume Flow Rate [m3/s] !Hourly': 'Linkage Flow out',
                'AFN Linkage Node 2 to Node 1 Volume Flow Rate [m3/s] !Hourly': 'Linkage Flow in',
                'AFN Surface Venting Window or Door Opening Factor [] !Hourly': 'Opening Factor'}
    hdict = {}
    
    for l, line in enumerate(lines):
        linesplit = line.strip('\n').split(',')
        if len(linesplit) > 3:
            if linesplit[2] == 'Day of Simulation[]':
                hdict[linesplit[0]] = ['Time'] 
            elif linesplit[3] in envdict:
                hdict[linesplit[0]] = ['Climate',  '', envdict[linesplit[3]]]  
            elif linesplit[3] in zresdict:
                hdict[linesplit[0]] = ['Zone',  retzonename(linesplit[2]),  zresdict[linesplit[3]]]
            elif linesplit[3] in enresdict:
                hdict[linesplit[0]] = ['External',  linesplit[2],  enresdict[linesplit[3]]]
            elif linesplit[3] in lresdict:
                hdict[linesplit[0]] = ['Linkage',  linesplit[2],  lresdict[linesplit[3]]]
        if line == 'End of Data Dictionary\n':
            break
    return hdict,  l + 1
    
def retzonename(zn):
    if  zn[-10:] == '_OCCUPANCY':
        return zn.strip('_OCCUPANCY')
    elif zn[-4:] == '_AIR':
        return zn.strip('_AIR')
    else:
        return zn
        
def processf(pro_op, scene, node):
    reslists = []
    frames = range(scene['enparams']['fs'], scene['enparams']['fe'] + 1)

    for frame in frames:
        with open(os.path.join(scene['viparams']['newdir'], '{}{}out.eso'.format(pro_op.resname, frame)), 'r') as resfile:
            lines = resfile.readlines()
            hdict, lstart = processh(lines)          
            bodylines = lines[lstart:-2]            
            bdict = {li: ' '.join([line.strip('\n').split(',')[1] for line in bodylines if line.strip('\n').split(',')[0] == li]) for li in hdict}
            
#            if len(frames) > 1:
#                reslists.append(['All', 'Frame', 'Number', 'Frame', str(frame)])
                
            for k in sorted(hdict.keys(), key=int):
                if hdict[k] == ['Time']:
                    reslists.append([str(frame), 'Time', '', 'Month', ' '.join([line.strip('\n').split(',')[2] for line in bodylines if line.strip('\n').split(',')[0] == k])])
                    reslists.append([str(frame), 'Time', '', 'Day', ' '.join([line.strip('\n').split(',')[3] for line in bodylines if line.strip('\n').split(',')[0] == k])])
                    reslists.append([str(frame), 'Time', '', 'Hour', ' '.join([line.strip('\n').split(',')[5] for line in bodylines if line.strip('\n').split(',')[0] == k])])
                    reslists.append([str(frame), 'Time', '', 'DOS', ' '.join([line.strip('\n').split(',')[1] for line in bodylines if line.strip('\n').split(',')[0] == k])])
                else:
                    reslists.append([str(frame)] + hdict[k] + [bdict[k]])
                
    if len(frames) > 1:
        rls = reslists
        zrls = list(zip(*rls))
        reslists.append(['All', 'Frames', '', 'Frames', ' '.join([str(f) for f in frames])])
        temps = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'Temperature (degC)']
        heats = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'Heating (W)']
        cools = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'Cooling (W)']
        aheats = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'Air Heating (W)']
        acools = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'Air Cooling (W)']
        co2s = [(zrls[2][zi], [float(t) for t in zrls[4][zi].split()]) for zi, z in enumerate(zrls[1]) if z == 'Zone' and zrls[3][zi] == 'CO2 (ppm)']

        for zn in set([t[0] for t in temps]):
            if temps:
                reslists.append(['All', 'Zone', zn, 'Max temp (C)', ' '.join([str(max(t[1])) for t in temps if t[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Min temp (C)', ' '.join([str(min(t[1])) for t in temps if t[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave temp (C)', ' '.join([str(sum(t[1])/len(t[1])) for t in temps if t[0] == zn])])
            if heats:
                reslists.append(['All', 'Zone', zn, 'Max heat (W)', ' '.join([str(max(h[1])) for h in heats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Min heat (W)', ' '.join([str(min(h[1])) for h in heats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave heat (W)', ' '.join([str(sum(h[1])/len(h[1])) for h in heats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Heating (kWh)', ' '.join([str(sum(h[1])*0.001) for h in heats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Heating (kWh/m2)', ' '.join([str(sum(h[1])*0.001/[o for o in bpy.data.objects if o.name.upper() == zn][0]['floorarea']) for h in heats if h[0] == zn])])
            if cools:
                reslists.append(['All', 'Zone', zn, 'Max cool (W)', ' '.join([str(max(h[1])) for h in cools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Min cool (W)', ' '.join([str(min(h[1])) for h in cools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave cool (W)', ' '.join([str(sum(h[1])/len(h[1])) for h in cools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Cooling (kWh)', ' '.join([str(sum(h[1])*0.001) for h in cools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Cooling (kWh/m2)', ' '.join([str(sum(h[1])*0.001/[o for o in bpy.data.objects if o.name.upper() == zn][0]['floorarea']) for h in cools if h[0] == zn])])
            if aheats:
                reslists.append(['All', 'Zone', zn, 'Max air heat (W)', ' '.join([str(max(h[1])) for h in aheats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Min air heat (W)', ' '.join([str(min(h[1])) for h in aheats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave air heat (W)', ' '.join([str(sum(h[1])/len(h[1])) for h in aheats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Air heating (kWh)', ' '.join([str(sum(h[1])*0.001) for h in aheats if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ait heating (kWh/m2)', ' '.join([str(sum(h[1])*0.001/[o for o in bpy.data.objects if o.name.upper() == zn][0]['floorarea']) for h in aheats if h[0] == zn])])
            if acools:
                reslists.append(['All', 'Zone', zn, 'Max air cool (W)', ' '.join([str(max(h[1])) for h in acools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Mina ir cool (W)', ' '.join([str(min(h[1])) for h in acools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave air cool (W)', ' '.join([str(sum(h[1])/len(h[1])) for h in acools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Air cooling (kWh)', ' '.join([str(sum(h[1])*0.001) for h in acools if h[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Air cooling (kWh/m2)', ' '.join([str(sum(h[1])*0.001/[o for o in bpy.data.objects if o.name.upper() == zn][0]['floorarea']) for h in acools if h[0] == zn])])
            if co2s:
                reslists.append(['All', 'Zone', zn, 'Max CO2 (ppm)', ' '.join([str(max(t[1])) for t in co2s if t[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Min CO2 (ppm)', ' '.join([str(min(t[1])) for t in co2s if t[0] == zn])])
                reslists.append(['All', 'Zone', zn, 'Ave Co2 (ppm)', ' '.join([str(sum(t[1])/len(t[1])) for t in co2s if t[0] == zn])])
                                                                                                         
    node['reslists'] = reslists
    
    if node.outputs['Results out'].links:
       node.outputs['Results out'].links[0].to_node.update() 

def iprop(iname, idesc, imin, imax, idef):
    return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef))
def eprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef))
def bprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef))
def sprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef))
def fprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef))
def fvprop(fvsize, fvname, fvattr, fvdef, fvsub, fvmin, fvmax):
    return(FloatVectorProperty(size = fvsize, name = fvname, attr = fvattr, default = fvdef, subtype =fvsub, min = fvmin, max = fvmax))
def niprop(iname, idesc, imin, imax, idef):
        return(IntProperty(name = iname, description = idesc, min = imin, max = imax, default = idef, update = nodeexported))
def neprop(eitems, ename, edesc, edef):
    return(EnumProperty(items=eitems, name = ename, description = edesc, default = edef, update = nodeexported))
def nbprop(bname, bdesc, bdef):
    return(BoolProperty(name = bname, description = bdesc, default = bdef, update = nodeexported))
def nsprop(sname, sdesc, smaxlen, sdef):
    return(StringProperty(name = sname, description = sdesc, maxlen = smaxlen, default = sdef, update = nodeexported))
def nfprop(fname, fdesc, fmin, fmax, fdef):
    return(FloatProperty(name = fname, description = fdesc, min = fmin, max = fmax, default = fdef, update = nodeexported))
def nfvprop(fvname, fvattr, fvdef, fvsub):
    return(FloatVectorProperty(name=fvname, attr = fvattr, default = fvdef, subtype = fvsub, update = nodeexported))

def boundpoly(obj, mat, poly, enng):
    if mat.envi_boundary:
        nodes = [node for node in enng.nodes if hasattr(node, 'zone') and node.zone == obj.name]
        for node in nodes:
            insock = node.inputs['{}_{}_b'.format(mat.name, poly.index)]
            outsock = node.outputs['{}_{}_b'.format(mat.name, poly.index)]              
            if insock.links:
                bobj = bpy.data.objects[insock.links[0].from_node.zone]
                bpoly = bobj.data.polygons[int(insock.links[0].from_socket.name.split('_')[-2])]
                if bobj.data.materials[bpoly.material_index] == mat:# and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                    return(("Surface", node.inputs['{}_{}_b'.format(mat.name, poly.index)].links[0].from_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))
        
            elif outsock.links:
                bobj = bpy.data.objects[outsock.links[0].to_node.zone]
                bpoly = bobj.data.polygons[int(outsock.links[0].to_socket.name.split('_')[-2])]
                if bobj.data.materials[bpoly.material_index] == mat:# and max(bpolyloc - polyloc) < 0.001 and abs(bpoly.area - poly.area) < 0.01:
                    return(("Surface", node.outputs['{}_{}_b'.format(mat.name, poly.index)].links[0].to_node.zone+'_'+str(bpoly.index), "NoSun", "NoWind"))
            return(("Outdoors", "", "SunExposed", "WindExposed"))

    elif mat.envi_thermalmass:
        return(("Adiabatic", "", "NoSun", "NoWind"))
    else:
        return(("Outdoors", "", "SunExposed", "WindExposed"))

def objvol(op, obj):
    bm , floor, roof, mesh = bmesh.new(), [], [], obj.data
    bm.from_object(obj, bpy.context.scene)
    for f in mesh.polygons:
        if obj.data.materials[f.material_index].envi_con_type == 'Floor':
            floor.append((facearea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
        elif obj.data.materials[f.material_index].envi_con_type == 'Roof':
            roof.append((facearea(obj, f), (obj.matrix_world*mathutils.Vector(f.center))[2]))
    zfloor = list(zip(*floor))
    if not zfloor and op:
        op.report({'INFO'},"Zone has no floor area")

    return(bm.calc_volume()*obj.scale[0]*obj.scale[1]*obj.scale[2])

def ceilheight(obj, vertz):
    mesh = obj.data
    for vert in mesh.vertices:
        vertz.append((obj.matrix_world * vert.co)[2])
    zmax, zmin = max(vertz), min(vertz)
    ceiling = [max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if max((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) > 0.9 * zmax]
    floor = [min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) for poly in mesh.polygons if min((obj.matrix_world * mesh.vertices[poly.vertices[0]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[1]].co)[2], (obj.matrix_world * mesh.vertices[poly.vertices[2]].co)[2]) < zmin + 0.1 * (zmax - zmin)]
    return(sum(ceiling)/len(ceiling)-sum(floor)/len(floor))

def vertarea(mesh, vert):
    area = 0
    faces = [face for face in vert.link_faces] 
    if hasattr(mesh.verts, "ensure_lookup_table"):
        mesh.verts.ensure_lookup_table()
    if len(faces) > 1:
        for f, face in enumerate(faces):
            ovs, oes = [], []
            fvs = [le.verts[(0, 1)[le.verts[0] == vert]] for le in vert.link_edges]
            ofaces = [oface for oface in faces if len([v for v in oface.verts if v in face.verts]) == 2]    
            for oface in ofaces:
                oes.append([e for e in face.edges if e in oface.edges])
                
                ovs.append([i for i in face.verts if i in oface.verts])
            
            if len(ovs) == 1:                
                sedgevs = (vert.index, [v.index for v in fvs if v not in ovs][0])
                sedgemp = mathutils.Vector([((mesh.verts[sedgevs[0]].co)[i] + (mesh.verts[sedgevs[1]].co)[i])/2 for i in range(3)])
                eps = [mathutils.geometry.intersect_line_line(face.calc_center_median(), ofaces[0].calc_center_median(), ovs[0][0].co, ovs[0][1].co)[1]] + [sedgemp]
            elif len(ovs) == 2:
                eps = [mathutils.geometry.intersect_line_line(face.calc_center_median(), ofaces[i].calc_center_median(), ovs[i][0].co, ovs[i][1].co)[1] for i in range(2)]
            else:
               return 0
            area += mathutils.geometry.area_tri(vert.co, *eps) + mathutils.geometry.area_tri(face.calc_center_median(), *eps)
    elif len(faces) == 1:
        eps = [(ev.verts[0].co +ev.verts[1].co)/2 for ev in vert.link_edges]
        eangle = (vert.link_edges[0].verts[0].co - vert.link_edges[0].verts[1].co).angle(vert.link_edges[1].verts[0].co - vert.link_edges[1].verts[1].co)
        area = mathutils.geometry.area_tri(vert.co, *eps) + mathutils.geometry.area_tri(faces[0].calc_center_median(), *eps) * 2*pi/eangle
    return area       

def facearea(obj, face):
    omw = obj.matrix_world
    vs = [omw*mathutils.Vector(face.center)] + [omw*obj.data.vertices[v].co for v in face.vertices] + [omw*obj.data.vertices[face.vertices[0]].co]
    return(vsarea(obj, vs))

def vsarea(obj, vs):
    if len(vs) == 5:
        cross = mathutils.Vector.cross(vs[3]-vs[1], vs[3]-vs[2])
        return(0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5)
    else:
        i, area = 0, 0
        while i < len(vs) - 2:
            cross = mathutils.Vector.cross(vs[0]-vs[1+i], vs[0]-vs[2+i])
            area += 0.5*(cross[0]**2 + cross[1]**2 +cross[2]**2)**0.5
            i += 1
        return(area)

def wind_rose(maxws, wrsvg, wrtype):
    pa, zp, lpos, scene, vs = 0, 0, [], bpy.context.scene, []    
    bm = bmesh.new()
    wrme = bpy.data.meshes.new("Wind_rose")   
    wro = bpy.data.objects.new('Wind_rose', wrme)     
    scene.objects.link(wro)
    scene.objects.active = wro
    wro.select, wro.location = True, (0, 0 ,0)
    
    with open(wrsvg, 'r') as svgfile:  
        svglines = svgfile.readlines()     
        for line in svglines:
            if "<svg height=" in line:
                dimen = int(line.split('"')[1].strip('pt'))
                scale = 0.04 * dimen
            if '/>' in line:
                lcolsplit = line.split(';')
                for lcol in lcolsplit: 
                    if 'style="fill:#' in lcol and lcol[-6:] != 'ffffff':
                        fillrgb = colors.hex2color(lcol[-7:])
                        if 'wr-{}'.format(lcol[-6:]) not in [mat.name for mat in bpy.data.materials]:
                            bpy.data.materials.new('wr-{}'.format(lcol[-6:]))
                        bpy.data.materials['wr-{}'.format(lcol[-6:])].diffuse_color = fillrgb
                        if 'wr-{}'.format(lcol[-6:]) not in [mat.name for mat in wro.data.materials]:
                            bpy.ops.object.material_slot_add()
                            wro.material_slots[-1].material = bpy.data.materials['wr-{}'.format(lcol[-6:])]  
                
        for line in svglines:
            linesplit = line.split(' ')
            if '<path' in line:
                pa = 1
            if pa and line[0] == 'M':
                spos = [((float(linesplit[0][1:])- dimen/2) * 0.1, (float(linesplit[1]) - dimen/2) * -0.1, 0.05)]
            if pa and line[0] == 'L':
                lpos.append(((float(linesplit[0][1:]) - dimen/2) * 0.1, (float(linesplit[1].strip('"')) - dimen/2) *-0.1, 0.05))
            if pa and '/>' in line:
                lcolsplit = line.split(';')
                for lcol in lcolsplit:                
                    if 'style="fill:#' in lcol and lcol[-6:] != 'ffffff':
                        for pos in spos + lpos[::-1]:
                            vs.append(bm.verts.new(pos))                        
                        if len(vs) > 2:
                            nf = bm.faces.new(vs)
                            nf.material_index = wro.data.materials[:].index(wro.data.materials['wr-{}'.format(lcol[-6:])])                            
                            if wrtype in ('2', '3', '4'):
                                zp += 0.0005 * scale 
                                for vert in nf.verts:
                                    vert.co[2] = zp
                bmesh.ops.remove_doubles(bm, verts=vs, dist = scale * 0.01)
                pa, lpos, vs = 0, [], []  

            if 'wr-000000' not in [mat.name for mat in bpy.data.materials]:
                bpy.data.materials.new('wr-000000')
            bpy.data.materials['wr-000000'].diffuse_color = (0, 0, 0)
            if 'wr-000000' not in [mat.name for mat in wro.data.materials]:
                bpy.ops.object.material_slot_add()
                wro.material_slots[-1].material = bpy.data.materials['wr-000000']
            

    if wrtype in ('0', '1', '3', '4'):            
        thick = scale * 0.005 if wrtype == '4' else scale * 0.0025
        faces = bmesh.ops.inset_individual(bm, faces=bm.faces, thickness = thick, use_even_offset = True)['faces']
        if wrtype == '4':
            [bm.faces.remove(f) for f in bm.faces if f not in faces]
        else:
            for face in faces:
                face.material_index = wro.data.materials[:].index(wro.data.materials['wr-000000'])

    bm.to_mesh(wro.data)
    bm.free()
    
    bpy.ops.mesh.primitive_circle_add(vertices = 132, fill_type='NGON', radius=scale*1.2, view_align=False, enter_editmode=False, location=(0, 0, -0.01))
    wrbo = bpy.context.active_object
    if 'wr-base'not in [mat.name for mat in bpy.data.materials]:
        bpy.data.materials.new('wr-base')
        bpy.data.materials['wr-base'].diffuse_color = (1,1,1)
    bpy.ops.object.material_slot_add()
    wrbo.material_slots[-1].material = bpy.data.materials['wr-base']
    return (objoin((wrbo, wro)), scale)
    
def compass(loc, scale, wro, mat):
    txts = []
    come = bpy.data.meshes.new("Compass")   
    coo = bpy.data.objects.new('Compass', come)
    coo.location = loc
    bpy.context.scene.objects.link(coo)
    bpy.context.scene.objects.active = coo
    bpy.ops.object.material_slot_add()
    coo.material_slots[-1].material = mat
    bm = bmesh.new()
    matrot = Matrix.Rotation(pi*0.25, 4, 'Z')
    
    for i in range(1, 11):
        bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*((i**2)/10)*0.1, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*1.075, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    bmesh.ops.create_circle(bm, cap_ends=False, diameter=scale*1.175, segments=132,  matrix=Matrix.Rotation(pi/64, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    
    for edge in bm.edges:
        edge.select_set(False) if edge.index % 3 or edge.index > 1187 else edge.select_set(True)
    
    bmesh.ops.delete(bm, geom = [edge for edge in bm.edges if edge.select], context = 2)
    newgeo = bmesh.ops.extrude_edge_only(bm, edges = bm.edges, use_select_history=False)
    
    for v, vert in enumerate(newgeo['geom'][:1584]):
        vert.co = vert.co - (vert.co - coo.location).normalized() * scale * (0.0025, 0.005)[v > 1187]
        vert.co[2] = 0
           
    bmesh.ops.create_circle(bm, cap_ends=True, diameter=scale *0.005, segments=8, matrix=Matrix.Rotation(-pi/8, 4, 'Z')*Matrix.Translation((0, 0, 0)))
    matrot = Matrix.Rotation(pi*0.25, 4, 'Z')
    degmatrot = Matrix.Rotation(pi*0.125, 4, 'Z')
    tmatrot = Matrix.Rotation(0, 4, 'Z')
    direc = Vector((0, 1, 0))

    for i, edge in enumerate(bm.edges[-8:]):
        verts = bmesh.ops.extrude_edge_only(bm, edges = [edge], use_select_history=False)['geom'][:2]
        for vert in verts:
            vert.co += 1.0*scale*(tmatrot*direc)
            vert.co[2] = 0
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=Vector(loc) + scale*1.1*(tmatrot*direc), rotation=tmatrot.to_euler())
        txt = bpy.context.active_object
        txt.scale, txt.data.body, txt.data.align, txt.location[2]  = (scale*0.075, scale*0.075, scale*0.075), ('N', 'NW', 'W', 'SW', 'S', 'SE', 'E', 'NE')[i], 'CENTER', txt.location[2]
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = mat
        txts.append(txt)
        tmatrot = tmatrot * matrot

    tmatrot = Matrix.Rotation(0, 4, 'Z')
    for d in range(16):
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=Vector(loc) + scale*1.0125*(tmatrot*direc), rotation=tmatrot.to_euler())
        txt = bpy.context.active_object
        txt.scale, txt.data.body, txt.data.align, txt.location[2]  = (scale*0.05, scale*0.05, scale*0.05), (u'0\u00B0', u'337.5\u00B0', u'315\u00B0', u'292.5\u00B0', u'270\u00B0', u'247.5\u00B0', u'225\u00B0', u'202.5\u00B0', u'180\u00B0', u'157.5\u00B0', u'135\u00B0', u'112.5\u00B0', u'90\u00B0', u'67.5\u00B0', u'45\u00B0', u'22.5\u00B0')[d], 'CENTER', txt.location[2]
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = mat
        txts.append(txt)
        tmatrot = tmatrot * degmatrot
    
    bm.to_mesh(come)
    bm.free()

    return txts + [coo] + [wro]

def spathrange(mats):
    sprme = bpy.data.meshes.new("SPRange")   
    spro = bpy.data.objects.new('SPRrange', sprme)
    bpy.context.scene.objects.link(spro)
    bpy.context.scene.objects.active = spro
    spro.location = (0, 0, 0)
    bm = bmesh.new()
    for params in ((177, 0.05, 0), (80, 0.1, 1), (355, 0.15, 2)):
        bpy.ops.object.material_slot_add()
        spro.material_slots[-1].material = mats[params[2]]
        morn = solarRiseSet(params[0], 0, bpy.context.scene.latitude, bpy.context.scene.longitude, 'morn')
        eve = solarRiseSet(params[0], 0, bpy.context.scene.latitude, bpy.context.scene.longitude, 'eve')
        angrange = [morn + a * 0.025 * (eve - morn) for a in range (0, 41)]
        bm.verts.new().co = (95*sin(angrange[0]*pi/180), 95*cos(angrange[0]*pi/180), params[1])
    
        for a in angrange[1:-1]:
            bm.verts.new().co = (92*sin(a*pi/180), 92*cos(a*pi/180), params[1])
        bm.verts.new().co = (95*sin(angrange[len(angrange) - 1]*pi/180), 95*cos(angrange[len(angrange) - 1]*pi/180), params[1])
        angrange.reverse()
        for b in angrange[1:-1]:
            bm.verts.new().co = (98*sin(b*pi/180), 98*cos(b*pi/180), params[1])

        bm.faces.new(bm.verts[-80:])
        bm.faces.ensure_lookup_table()
        bm.faces[-1].material_index = params[2]
    bm.to_mesh(sprme)
    bm.free()
    return spro

def windnum(maxws, loc, scale, wr):
    txts = []
    matrot = Matrix.Rotation(-pi*0.125, 4, 'Z')
    direc = Vector((0, 1, 0))
    for i in range(5):
        bpy.ops.object.text_add(view_align=False, enter_editmode=False, location=((i+1)/5)*scale*(matrot*direc))
        txt = bpy.context.active_object
        txt.data.body, txt.scale, txt.location[2] = '{:.1f}'.format((i+1)*maxws/5), (scale*0.05, scale*0.05, scale*0.05), scale*0.01
        bpy.ops.object.convert(target='MESH')
        bpy.ops.object.material_slot_add()
        txt.material_slots[-1].material = bpy.data.materials['wr-000000']
        txts.append(txt)
    objoin(txts + [wr]).name = 'Wind Rose'
    bpy.context.active_object['VIType']  = 'Wind_Plane'
    
def rgb2h(rgb):
    return colorsys.rgb_to_hsv(rgb[0]/255.0,rgb[1]/255.0,rgb[2]/255.0)[0]

def livisimacc(simnode):
    context = simnode.inputs['Context in'].links[0].from_node['Options']['Context']
    return(simnode.csimacc if context in ('Compliance', 'CBDM') else simnode.simacc)

def drawpoly(x1, y1, x2, y2, a, r, g, b):
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(r, g, b, a)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    
def drawtri(posx, posy, l, d, hscale, radius):
    r, g, b = colorsys.hsv_to_rgb(0.75 - l * 0.75, 1.0, 1.0)
    a = 0.9
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBegin(bgl.GL_POLYGON)
    bgl.glColor4f(r, g, b, a)
    bgl.glVertex2f(posx - l * 0.5  * hscale *(radius - 20)*sin(d*pi/180), posy - l * 0.5 * hscale * (radius - 20)*cos(d*pi/180)) 
    bgl.glVertex2f(posx + hscale * (l**0.5) *(radius/4 - 5)*cos(d*pi/180), posy - hscale * (l**0.5) *(radius/4 - 5)*sin(d*pi/180))    
    bgl.glVertex2f(posx + l**0.5 * hscale *(radius - 20)*sin(d*pi/180), posy + l**0.5 * hscale * (radius - 20)*cos(d*pi/180)) 
    bgl.glVertex2f(posx - hscale * (l**0.5) *(radius/4 - 5)*cos(d*pi/180), posy + hscale * (l**0.5) *(radius/4 - 5)*sin(d*pi/180))
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)
    
def drawcircle(center, radius, resolution, fill, a, r, g, b):
    bgl.glColor4f(r, g, b, a)
    bgl.glEnable(bgl.GL_LINE_SMOOTH)
    bgl.glEnable(bgl.GL_BLEND);
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    bgl.glHint(bgl.GL_LINE_SMOOTH_HINT, bgl.GL_NICEST)
    bgl.glLineWidth (1.5)
    if fill:
        bgl.glBegin(bgl.GL_POLYGON)
    else:
        bgl.glBegin(bgl.GL_LINE_STRIP)

    for i in range(resolution+1):
        vec = Vector((cos(i/resolution*2*pi), sin(i/resolution*2*pi)))
        v = vec * radius + center
        bgl.glVertex2f(v.x, v.y)
    bgl.glEnd()

def drawloop(x1, y1, x2, y2):
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    bgl.glVertex2i(x1, y2)
    bgl.glVertex2i(x2, y2)
    bgl.glVertex2i(x2, y1)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()

def drawfont(text, fi, lencrit, height, x1, y1):
    blf.position(fi, x1, height - y1 - lencrit*26, 0)
    blf.draw(fi, text)
    
def mtx2vals(mtxlines, fwd, node):
    for m, mtxline in enumerate(mtxlines):
        if 'NROWS' in mtxline:
            patches = int(mtxline.split('=')[1])
        elif 'NCOLS' in mtxline:
            hours = int(mtxline.split('=')[1])
        elif mtxline == '\n':
            startline = m + 1
            break

    vecvals, vals, hour, patch = array([[x%24, (fwd+int(x/24))%7] + [0 for p in range(patches)] for x in range(hours)]), zeros((patches)), 0, 2
    
    for fvals in mtxlines[startline:]:
        if fvals == '\n':
            patch += 1
            hour = 0
        else:
            sumvals = sum([float(lv) for lv in fvals.split(" ") if not isnan(eval(lv))])/3
            if sumvals > 0:
                vals[patch - 2] += sumvals
                vecvals[hour][patch] = sumvals
            hour += 1
    return(vecvals.tolist(), vals)

def bres(scene, o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if scene['liparams']['cp'] == '1':
        rtlayer = bm.verts.layers.int['cindex']
        reslayer = bm.verts.layers.float['res{}'.format(scene.frame_current)]
        res = [v[reslayer] for v in bm.verts if v[rtlayer] > 0]
    elif scene['liparams']['cp'] == '0':
        rtlayer = bm.faces.layers.int['cindex']
        reslayer = bm.faces.layers.float['res{}'.format(scene.frame_current)]
        res = [f[reslayer] for f in bm.faces if f[rtlayer] > 0]
    bm.free()
    return res
    
def framerange(scene, anim):
    if anim == 'Static':
        return(range(scene.frame_current, scene.frame_current +1))
    else:
        return(range(scene.frame_start, scene['liparams']['fe'] + 1))

def frameindex(scene, anim):
    if anim == 'Static':
        return(range(0, 1))
    else:
        return(range(0, scene.frame_end - scene.frame_start +1))

def retobjs(otypes):
    scene = bpy.context.scene
    validobs = [o for o in scene.objects if o.hide == False and o.layers[scene.active_layer] == True]
    if otypes == 'livig':
        return([o for o in validobs if o.type == 'MESH' and o.data.materials and not (o.parent and os.path.isfile(o.ies_name)) and not o.vi_type == '4' \
        and o.lires == 0 and o.get('VIType') not in ('SPathMesh', 'SunMesh', 'Wind_Plane', 'SkyMesh')])
    elif otypes == 'livigeno':
        return([o for o in validobs if o.type == 'MESH' and o.data.materials and not any([m.livi_sense for m in o.data.materials])])
    elif otypes == 'livigengeosel':
        return([o for o in validobs if o.type == 'MESH' and o.select == True and o.data.materials and not any([m.livi_sense for m in o.data.materials])])
    elif otypes == 'livil':
        return([o for o in validobs if (o.type == 'LAMP' or o.vi_type == '4') and o.hide == False and o.layers[scene.active_layer] == True])
    elif otypes == 'livic':
        return([o for o in validobs if o.type == 'MESH' and li_calcob(o, 'livi') and o.lires == 0 and o.hide == False and o.layers[scene.active_layer] == True])
    elif otypes == 'livir':
        return([o for o in validobs if o.type == 'MESH' and True in [m.livi_sense for m in o.data.materials] and o.licalc and o.layers[scene.active_layer] == True])
    elif otypes == 'envig':
        return([o for o in validobs if o.type == 'MESH' and o.hide == False and o.layers[0] == True])
    elif otypes == 'ssc':
        return [o for o in validobs if o.type == 'MESH' and o.lires == 0 and o.hide == False and o.layers[scene.active_layer] == True and any([m.mattype == '2' for m in o.data.materials])]

def radmesh(scene, obs, export_op):
    for o in obs:
        for mat in o.data.materials:
            if mat['radentry'] and mat['radentry'].split(' ')[1] in ('light', 'mirror', 'antimatter') or mat.pport:
                export_op.report({'INFO'}, o.name+" has an antimatter, photon port, emission or mirror material. Basic export routine used with no modifiers.")
                o['merr'] = 1 
        selobj(scene, o)
        selmesh('selenm')                        
        if [edge for edge in o.data.edges if edge.select]:
            export_op.report({'INFO'}, o.name+" has a non-manifold mesh. Basic export routine used with no modifiers.")
            o['merr'] = 1
        if not o.get('merr'):
            o['merr'] = 0

def viewdesc(context):
    region = context.region
    width, height = region.width, region.height
    mid_x, mid_y = width/2, height/2
    return(mid_x, mid_y, width, height)
    
def skfpos(o, frame, vis):
    vcos = [o.matrix_world*o.data.shape_keys.key_blocks[str(frame)].data[v].co for v in vis]
    maxx = max([vco[0] for vco in vcos])
    minx = min([vco[0] for vco in vcos])
    maxy = max([vco[1] for vco in vcos])
    miny = min([vco[1] for vco in vcos])
    maxz = max([vco[2] for vco in vcos])
    minz = min([vco[2] for vco in vcos])
    return mathutils.Vector(((maxx + minx) * 0.5, (maxy + miny) * 0.5, (maxz + minz) * 0.5))

def selmesh(sel):
    if bpy.context.active_object.mode != 'EDIT':
        bpy.ops.object.mode_set(mode = 'EDIT')        
    if sel == 'selenm':
        bpy.ops.mesh.select_mode(type="EDGE")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold()
    elif sel == 'desel':
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel in ('delf', 'rd'):
        if sel == 'delf':
            bpy.ops.mesh.delete(type = 'FACE')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.mesh.select_all(action='DESELECT')
    elif sel in ('SELECT', 'INVERT', 'PASS'):
        if sel in ('SELECT', 'INVERT'):
            bpy.ops.mesh.select_all(action=sel)    
        bpy.ops.object.vertex_group_assign()
    bpy.ops.object.mode_set(mode = 'OBJECT')

def draw_index(context, leg, mid_x, mid_y, width, height, posis, res):
    vecs = [mathutils.Vector((vec[0] / vec[3], vec[1] / vec[3], vec[2] / vec[3])) for vec in posis]
    bds = [blf.dimensions(0, ('{:.1f}', '{:.0f}')[r > 100 or context.scene['viparams']['resnode'] == 'VI Sun Path'].format(r)) for r in res]
    xs = [int(mid_x + vec[0] * mid_x) for vec in vecs]
    ys = [int(mid_y + vec[1] * mid_y) for vec in vecs]
    [(blf.position(0, xs[ri] - int(0.5*bds[ri][0]), ys[ri] - int(0.5 * bds[ri][1]), 0), blf.draw(0, ('{:.1f}', '{:.0f}')[r > 100 or context.scene['viparams']['resnode'] == 'VI Sun Path'].format(r))) for ri, r in enumerate(res) if (leg == 1 and (xs[ri] > 120 or ys[ri] < height - 530)) or leg == 0]

def draw_time(context, mid_x, mid_y, width, height, pos, time):
    vec = mathutils.Vector((pos[0] / pos[3], pos[1] / pos[3], pos[2] / pos[3]))
    x = int(mid_x + vec[0] * mid_x) 
    y = int(mid_y + vec[1] * mid_y)
    blf.position(0, x, y, 0)
    blf.draw(0, time)
        
def edgelen(ob, edge):
    omw = ob.matrix_world
    vdiff = omw * (ob.data.vertices[edge.vertices[0]].co - ob.data.vertices[edge.vertices[1]].co)
    mathutils.Vector(vdiff).length

def sunpath1(self, context):
    sunpath()

def sunpath2(scene):
    sunpath()

def sunpath():
    scene = bpy.context.scene
    suns = [ob for ob in scene.objects if ob.get('VIType') == 'Sun']
    skyspheres = [ob for ob in scene.objects if ob.get('VIType') == 'SkyMesh']
    
    if suns and 0 in (suns[0]['solhour'] == scene.solhour, suns[0]['solday'] == scene.solday):
        sunobs = [ob for ob in scene.objects if ob.get('VIType') == 'SunMesh']
        spathobs = [ob for ob in scene.objects if ob.get('VIType') == 'SPathMesh']
        beta, phi = solarPosition(scene.solday, scene.solhour, scene.latitude, scene.longitude)[2:]
        if spathobs:
            suns[0].location.z = spathobs[0].location.z + 100 * sin(beta)
            suns[0].location.x = spathobs[0].location.x -(100**2 - (suns[0].location.z-spathobs[0].location.z)**2)**0.5 * sin(phi)
            suns[0].location.y = spathobs[0].location.y -(100**2 - (suns[0].location.z-spathobs[0].location.z)**2)**0.5 * cos(phi)
        suns[0].rotation_euler = pi * 0.5 - beta, 0, -phi

        if scene.render.engine == 'CYCLES':
            if scene.world.node_tree:
                for stnode in [no for no in scene.world.node_tree.nodes if no.bl_label == 'Sky Texture']:
                    stnode.sun_direction = -sin(phi), -cos(phi), sin(beta)
            if suns[0].data.node_tree:
                for blnode in [node for node in suns[0].data.node_tree.nodes if node.bl_label == 'Blackbody']:
                    blnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5 if beta > 0 else 2500
                for emnode in [node for node in suns[0].data.node_tree.nodes if node.bl_label == 'Emission']:
                    emnode.inputs[1].default_value = 10 * sin(beta)**0.5 if beta > 0 else 0
            if sunobs and sunobs[0].data.materials[0].node_tree:
                for smblnode in [node for node in sunobs[0].data.materials[0].node_tree.nodes if sunobs[0].data.materials and node.bl_label == 'Blackbody']:
                    smblnode.inputs[0].default_value = 2500 + 3000*sin(beta)**0.5 if beta > 0 else 2500
            if skyspheres and not skyspheres[0].hide and skyspheres[0].data.materials[0].node_tree:
                for stnode in [no for no in skyspheres[0].data.materials[0].node_tree.nodes if no.bl_label == 'Sky Texture']:
                    stnode.sun_direction = sin(phi), -cos(phi), sin(beta)

        suns[0]['solhour'], suns[0]['solday'] = scene.solhour, scene.solday
        return

def epwlatilongi(scene, node):
    with open(node.weather, "r") as epwfile:
        fl = epwfile.readline()
        latitude, longitude = float(fl.split(",")[6]), float(fl.split(",")[7])
    return latitude, longitude

#Compute solar position (altitude and azimuth in degrees) based on day of year (doy; integer), local solar time (lst; decimal hours), latitude (lat; decimal degrees), and longitude (lon; decimal degrees).
def solarPosition(doy, lst, lat, lon):
    #Set the local standard time meridian (lsm) (integer degrees of arc)
    lsm = round(lon/15, 0)*15
    #Approximation for equation of time (et) (minutes) comes from the Wikipedia article on Equation of Time
    b = 2*pi*(doy-81)/364
    et = 9.87 * sin(2*b) - 7.53 * cos(b) - 1.5 * sin(b)
    #The following formulas adapted from the 2005 ASHRAE Fundamentals, pp. 31.13-31.16
    #Conversion multipliers
    degToRad = 2*pi/360
    radToDeg = 1/degToRad
    #Apparent solar time (ast)
    if lon > lsm: 
        ast = lst + et/60 - (lsm-lon)/15
    else:
        ast = lst + et/60 + (lsm-lon)/15
    #Solar declination (delta) (radians)
    delta = degToRad*23.45 * sin(2*pi*(284+doy)/365)
    #Hour angle (h) (radians)
    h = degToRad*15 * (ast-12)
     #Local latitude (l) (radians)
    l = degToRad*lat
    #Solar altitude (beta) (radians)
    beta = asin(cos(l) * cos(delta) * cos(h) + sin(l) * sin(delta))
    #Solar azimuth phi (radians)
    phi = acos((sin(beta) * sin(l) - sin(delta))/(cos(beta) * cos(l)))
    #Convert altitude and azimuth from radians to degrees, since the Spatial Analyst's Hillshade function inputs solar angles in degrees
    altitude = radToDeg*beta
    phi = 2*pi - phi if ast<=12 or ast >= 24 else phi
    azimuth = radToDeg*phi
    return([altitude, azimuth, beta, phi])
    
def solarRiseSet(doy, beta, lat, lon, riseset):
    degToRad = 2*pi/360
    radToDeg = 1/degToRad
    delta = degToRad*23.45 * sin(2*pi*(284+doy)/365)
    l = degToRad*lat
    phi = acos((sin(beta) * sin(l) - sin(delta))/(cos(beta) * cos(l)))
    phi = pi - phi if riseset == 'morn' else pi + phi
    return(phi*radToDeg)

def set_legend(ax):
    l = ax.legend(borderaxespad = -4)
    plt.setp(l.get_texts(), fontsize=8)

def wr_axes():
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor='w', edgecolor='w')
    rect = [0.1, 0.1, 0.8, 0.8]
    ax = WindroseAxes(fig, rect, axisbg='w')
    fig.add_axes(ax)
    return(fig, ax)

def skframe(pp, scene, oblist):
    for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
        scene.frame_set(frame)
        for o in [o for o in oblist if o.data.shape_keys]:
            for shape in o.data.shape_keys.key_blocks:
                if shape.name.isdigit():
                    shape.value = shape.name == str(frame)
                    shape.keyframe_insert("value")

def gentarget(tarnode, result):
    if tarnode.stat == '0':
        res = sum(result)/len(result)
    elif tarnode.stat == '1':
        res = max(result)
    elif tarnode.stat == '2':
        res = min(result)
    elif tarnode.stat == '3':
        res = sum(result)

    if tarnode.value > res and tarnode.ab == '0':
        return(1)
    elif tarnode.value < res and tarnode.ab == '1':
        return(1)
    else:
        return(0)

def selobj(scene, geo):
    if scene.objects.active and scene.objects.active.hide == 'False':
        bpy.ops.object.mode_set(mode = 'OBJECT') 
    for ob in scene.objects:
        ob.select = True if ob == geo else False
    scene.objects.active = geo

def nodeid(node):
    for ng in bpy.data.node_groups:
        if node in ng.nodes[:]:
            return node.name+'@'+ng.name

def nodecolour(node, prob):
    (node.use_custom_color, node.color) = (1, (1.0, 0.3, 0.3)) if prob else (0, (1.0, 0.3, 0.3))
    if prob:
        node.hide = False
    return not prob

def remlink(node, links):
    for link in links:
        bpy.data.node_groups[node['nodeid'].split('@')[1]].links.remove(link)

def epentry(header, params, paramvs):
    return '{}\n'.format(header+(',', '')[header == ''])+'\n'.join([('    ', '')[header == '']+'{:{width}}! - {}'.format(str(pv[0])+(',', ';')[pv[1] == params[-1]], pv[1], width = 80 + (0, 4)[header == '']) for pv in zip(paramvs, params)]) + ('\n\n', '')[header == '']

def sockhide(node, lsocknames):
    try:
        for ins in [insock for insock in node.inputs if insock.name in lsocknames]:
            node.outputs[ins.name].hide = True if ins.links else False
        for outs in [outsock for outsock in node.outputs if outsock.name in lsocknames]:
            node.inputs[outs.name].hide = True if outs.links else False
    except Exception as e:
        print('sockhide', e)

def socklink(sock, ng):
    try:
        valid1 = sock.valid if not sock.get('valid') else sock['valid']
        for link in sock.links:
            valid2 = link.to_socket.valid if not link.to_socket.get('valid') else link.to_socket['valid'] 
            valset = set(valid1)&set(valid2) 
            if not valset or len(valset) < min((len(valid1), len(valid2))):# or sock.node.use_custom_color:
                bpy.data.node_groups[ng].links.remove(link)
    except:
        if sock.links:
            bpy.data.node_groups[ng].links.remove(sock.links[-1])
    
def rettimes(ts, fs, us):
    tot = range(min(len(ts), len(fs), len(us)))
    fstrings, ustrings, tstrings = [[] for t in tot],  [[] for t in tot], ['Through: {}/{}'.format(dtdf(ts[t]).month, dtdf(ts[t]).day) for t in tot]
    for t in tot:
        fstrings[t]= ['For: '+''.join(f.strip()) for f in fs[t].split(' ') if f.strip(' ') != '']
        for uf, ufor in enumerate(us[t].split(';')):
            ustrings[t].append([])
            for ut, utime in enumerate(ufor.split(',')):
                ustrings[t][uf].append(['Until: '+','.join([u.strip() for u in utime.split(' ') if u.strip(' ')])])
    return(tstrings, fstrings, ustrings)
    
def epschedwrite(name, stype, ts, fs, us):
    params = ['Name', 'Schedule Type Limits Name']
    paramvs = [name, stype]
    for t in range(len(ts)):
        params.append('Field {}'.format(len(params)-2))
        paramvs .append(ts[t])
        for f in range(len(fs[t])):
            params.append('Field {}'.format(len(params)-2))
            paramvs.append(fs[t][f])
            for u in range(len(us[t][f])):
                params.append('Field {}'.format(len(params)-2))
                paramvs.append(us[t][f][u][0])
    return epentry('Schedule:Compact', params, paramvs)
    
def li_calcob(ob, li):
    if not ob.data.materials:
        return False
    else:
        ob.licalc = 1 if [face.index for face in ob.data.polygons if (ob.data.materials[face.material_index].mattype == '2', ob.data.materials[face.material_index].mattype == '1')[li == 'livi']] else 0
        return ob.licalc

# FloVi functions
def fvboundwrite(o):
    boundary = ''
    for mat in o.data.materials:        
        boundary += "  {}\n  {{\n    type {};\n    faces\n    (\n".format(mat.name, ("wall", "patch", "patch", "symmetryPlane", "empty")[int(mat.flovi_bmb_type)])#;\n\n"
        faces = [face for face in o.data.polygons if o.data.materials[face.material_index] == mat]
        for face in faces:
            boundary += "      ("+" ".join([str(v) for v in face.vertices])+")\n"
        boundary += "    );\n  }\n"
    boundary += ");\n\nmergePatchPairs\n(\n);"
    return boundary
    
def fvbmwrite(o, expnode):
    omw, bmovs = o.matrix_world, [vert for vert in o.data.vertices]
    xvec, yvec, zvec = (omw*bmovs[3].co - omw*bmovs[0].co).normalized(), (omw*bmovs[2].co - omw*bmovs[3].co).normalized(), (omw*bmovs[4].co - omw*bmovs[0].co).normalized() 
    ofvpos = [[(omw*bmov.co - omw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for bmov in bmovs]
    bmdict = "FoamFile\n  {\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      blockMeshDict;\n  }\n\nconvertToMeters 1.0;\n\n" 
    bmdict += "vertices\n(\n" + "\n".join(["  ({0:.3f} {1:.3f} {2:.3f})" .format(*ofvpo) for ofvpo in ofvpos]) +"\n);\n\n"
    bmdict += "blocks\n(\n  hex (0 3 2 1 4 7 6 5) ({} {} {}) simpleGrading ({} {} {})\n);\n\n".format(expnode.bm_xres, expnode.bm_yres, expnode.bm_zres, expnode.bm_xgrad, expnode.bm_ygrad, expnode.bm_zgrad) 
    bmdict += "edges\n(\n);\n\n"  
    bmdict += "boundary\n(\n" 
    bmdict += fvboundwrite(o)
    return bmdict
    
def fvblbmgen(mats, ffile, vfile, bfile, meshtype):
    scene = bpy.context.scene
    matfacedict = {mat.name:[0, 0] for mat in mats}
    
    for line in bfile.readlines():
        if line.strip() in matfacedict:
            mat = line.strip()
        elif '_' in line and line.strip().split('_')[1] in matfacedict:
            mat = line.strip().split('_')[1]
        if 'nFaces' in line:
            matfacedict[mat][1] = int(line.split()[1].strip(';'))
        if 'startFace' in line:
            matfacedict[mat][0] = int(line.split()[1].strip(';'))
    bobs = [ob for ob in scene.objects if ob.get('VIType') and ob['VIType'] == 'FloViMesh']
    
    if bobs:
        o = bobs[0]
        selobj(scene, o)
        while o.data.materials:
            bpy.ops.object.material_slot_remove()
    else:
        bpy.ops.object.add(type='MESH', layers=(False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, False, True))
        o = bpy.context.object
        o['VIType'] = 'FloViMesh'
    
    o.name = meshtype
    for mat in mats:
        if mat.name not in o.data.materials:
            bpy.ops.object.material_slot_add()
            o.material_slots[-1].material = mat 
    matnamedict = {mat.name: m for  m, mat in enumerate(o.data.materials)}
    
    bm = bmesh.new()
    for line in [line for line in vfile.readlines() if line[0] == '(' and len(line.split(' ')) == 3]:
        bm.verts.new().co = [float(vpos) for vpos in line[1:-2].split(' ')]
    if hasattr(bm.verts, "ensure_lookup_table"):
        bm.verts.ensure_lookup_table()
    for l, line in enumerate([line for line in ffile.readlines() if '(' in line and line[0].isdigit() and len(line.split(' ')) == int(line[0])]):
        newf = bm.faces.new([bm.verts[int(fv)] for fv in line[2:-2].split(' ')])
        for facerange in matfacedict.items():
            if l in range(facerange[1][0], facerange[1][0] + facerange[1][1]):
                newf.material_index = matnamedict[facerange[0]]
    bm.to_mesh(o.data)
    bm.free()

def fvbmr(scene, o):
    points = '{\n    version     2.0;\n    format      ascii;\n    class       vectorField;\n    location    "constant/polyMesh";\n    object      points;\n}\n\n{}\n(\n'.format(len(o.data.verts))
    points += ''.join(['({} {} {})\n'.format(o.matrix_world * v.co) for v in o.data.verts]) + ')'
    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'points'), 'r') as pfile:
        pfile.write(points)
    faces = '{\n    version     2.0;\n    format      ascii;\n    class       faceList;\n    location    "constant/polyMesh";\n    object      faces;\n}\n\n{}\n(\n'.format(len(o.data.faces))
    faces += ''.join(['({} {} {} {})\n'.format(f.vertices) for f in o.data.faces]) + ')'
    with open(os.path.join(scene['flparams']['ofcpfilebase'], 'faces'), 'r') as ffile:
        ffile.write(faces)
    
def fvvarwrite(scene, obs, node):
    '''Turbulence modelling: k and epsilon required for kEpsilon, k and omega required for kOmega, nutilda required for SpalartAllmaras, nut required for all
        Bouyancy modelling: T''' 
    (pentry, Uentry, nutildaentry, nutentry, kentry, eentry, oentry) = ["FoamFile\n{{\n  version     2.0;\n  format      ascii;\n  class       vol{}Field;\n  object      {};\n}}\n\ndimensions [0 {} {} 0 0 0 0];\ninternalField   uniform {};\n\nboundaryField\n{{\n".format(*var) for var in (('Scalar', 'p', '2', '-2', '{}'.format(node.pval)), ('Vector', 'U', '1', '-1' , '({} {} {})'.format(*node.uval)), ('Scalar', 'nuTilda', '2', '-1' , '{}'.format(node.nutildaval)), ('Scalar', 'nut', '2', '-1' , '{}'.format(node.nutval)), 
    ('Scalar', 'k', '2', '-2' , '{}'.format(node.kval)), ('Scalar', 'epsilon', '2', '-3' , '{}'.format(node.epval)), ('Scalar', 'omega', '0', '-1' , '{}'.format(node.oval)))]
    
    for o in obs:
        for mat in o.data.materials: 
            matname = '{}_{}'.format(o.name, mat.name) if o.vi_type == '3' else mat.name 
            if mat.mattype == '3':
                pentry += mat.fvmat(matname, 'p')
                Uentry += mat.fvmat(matname, 'U')
                if node.solver != 'icoFoam':
                    nutentry += mat.fvmat(matname, 'nut')
                    if node.turbulence ==  'SpalartAllmaras':
                        nutildaentry += mat.fvmat(matname, 'nutilda')
                    elif node.turbulence ==  'kEpsilon':
                        kentry += mat.fvmat(matname, 'k')
                        eentry += mat.fvmat(matname, 'e')
                    elif node.turbulence ==  'kOmega':
                        kentry += mat.fvmat(matname, 'k')
                        oentry += mat.fvmat(matname, 'o')

    pentry += '}'
    Uentry += '}'
    nutentry += '}'
    kentry += '}'
    eentry += '}'
    oentry += '}'
    
    with open(os.path.join(scene['flparams']['of0filebase'], 'p'), 'w') as pfile:
        pfile.write(pentry)
    with open(os.path.join(scene['flparams']['of0filebase'], 'U'), 'w') as Ufile:
        Ufile.write(Uentry)
    if node.solver != 'icoFoam':
        with open(os.path.join(scene['flparams']['of0filebase'], 'nut'), 'w') as nutfile:
            nutfile.write(nutentry)
        if node.turbulence == 'SpalartAllmaras':
            with open(os.path.join(scene['flparams']['of0filebase'], 'nuTilda'), 'w') as nutildafile:
                nutildafile.write(nutildaentry)
        if node.turbulence == 'kEpsilon':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'epsilon'), 'w') as efile:
                efile.write(eentry)
        if node.turbulence == 'kOmega':
            with open(os.path.join(scene['flparams']['of0filebase'], 'k'), 'w') as kfile:
                kfile.write(kentry)
            with open(os.path.join(scene['flparams']['of0filebase'], 'omega'), 'w') as ofile:
                ofile.write(oentry)
                
def fvmattype(mat, var):
    if mat.flovi_bmb_type == '0':
        matbptype = ['zeroGradient'][int(mat.flovi_bmwp_type)]
        matbUtype = ['fixedValue'][int(mat.flovi_bmwu_type)]
    elif mat.flovi_bmb_type in ('1', '2'):
        matbptype = ['freestreamPressure'][int(mat.flovi_bmiop_type)]
        matbUtype = ['fixedValue'][int(mat.flovi_bmiou_type)]
    elif mat.flovi_bmb_type == '3':
        matbptype = 'empty'
        matbUtype = 'empty'
    
def fvcdwrite(solver, dt, et):
    pw = 0 if solver == 'icoFoam' else 1
    return 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object      controlDict;\n}\n\n' + \
            'application     {};\nstartFrom       startTime;\nstartTime       0;\nstopAt          endTime;\nendTime         {};\n'.format(solver, et)+\
            'deltaT          {};\nwriteControl    timeStep;\nwriteInterval   {};\npurgeWrite      {};\nwriteFormat     ascii;\nwritePrecision  6;\n'.format(dt, 1, pw)+\
            'writeCompression off;\ntimeFormat      general;\ntimePrecision   6;\nrunTimeModifiable true;\n\n'

def fvsolwrite(node):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object    fvSolution;\n}\n\n' + \
        'solvers\n{\n  p\n  {\n    solver          PCG;\n    preconditioner  DIC;\n    tolerance       1e-06;\n    relTol          0;\n  }\n\n' + \
        '  "(U|k|epsilon|omega|R|nuTilda)"\n  {\n    solver          smoothSolver;\n    smoother        symGaussSeidel;\n    tolerance       1e-05;\n    relTol          0;  \n  }\n}\n\n'
    if node.solver == 'icoFoam':
        ofheader += 'PISO\n{\n  nCorrectors     2;\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n}\n\n' + \
        'solvers\n{\n    p\n    {\n        solver          GAMG;\n        tolerance       1e-06;\n        relTol          0.1;\n        smoother        GaussSeidel;\n' + \
        '        nPreSweeps      0;\n        nPostSweeps     2;\n        cacheAgglomeration true;\n        nCellsInCoarsestLevel 10;\n        agglomerator    faceAreaPair;\n'+ \
        '        mergeLevels     1;\n    }\n\n    U\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n        nSweeps         2;\n' + \
        '        tolerance       1e-08;\n        relTol          0.1;\n    }\n\n    nuTilda\n    {\n        solver          smoothSolver;\n        smoother        GaussSeidel;\n' + \
        '        nSweeps         2;\n        tolerance       1e-08;\n        relTol          0.1;\n    }\n}\n\n'
    elif node.solver == 'simpleFoam':   
        ofheader += 'SIMPLE\n{{\n  nNonOrthogonalCorrectors 0;\n  pRefCell        0;\n  pRefValue       0;\n\n    residualControl\n  {{\n    "(p|U|k|epsilon|omega|nut|nuTilda)" {};\n  }}\n}}\n'.format(node.convergence)
        ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
            '        U               0.7;\n        k               0.7;\n        epsilon           0.7;\n      omega           0.7;\n        nuTilda           0.7;\n    }\n}\n\n'
#        if node.turbulence == 'kEpsilon':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        epsilon           0.7;\n    }\n}\n\n'
#        elif node.turbulence == 'kOmega':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        omega           0.7;\n    }\n}\n\n'
#        elif node.turbulence == 'SpalartAllmaras':
#            ofheader += 'relaxationFactors\n{\n    fields\n    {\n        p               0.3;\n    }\n    equations\n    {\n' + \
#            '        U               0.7;\n        k               0.7;\n        nuTilda           0.7;\n    }\n}\n\n'
    return ofheader

def fvschwrite(node):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  location    "system";\n  object    fvSchemes;\n}\n\n'
    if node.solver == 'icoFoam':
        return ofheader + 'ddtSchemes\n{\n  default         Euler;\n}\n\ngradSchemes\n{\n  default         Gauss linear;\n  grad(p)         Gauss linear;\n}\n\n' + \
            'divSchemes\n{\n  default         none;\n  div(phi,U)      Gauss linear;\n}\n\nlaplacianSchemes\n{\n  default         Gauss linear orthogonal;\n}\n\n' + \
            'interpolationSchemes\n{\n  default         linear;\n}\n\n' + \
            'snGradSchemes{  default         orthogonal;}\n\nfluxRequired{  default         no;  p;\n}'
    else:
        ofheader += 'ddtSchemes\n{\n    default         steadyState;\n}\n\ngradSchemes\n{\n    default         Gauss linear;\n}\n\ndivSchemes\n{\n    '
        if node.turbulence == 'kEpsilon':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,epsilon)  bounded Gauss upwind;\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'kOmega':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss upwind;\n    div(phi,k)      bounded Gauss upwind;\n    div(phi,omega)  bounded Gauss upwind;\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        elif node.turbulence == 'SpalartAllmaras':
            ofheader += 'default         none;\n    div(phi,U)   bounded Gauss linearUpwind grad(U);\n    div(phi,nuTilda)      bounded Gauss linearUpwind grad(nuTilda);\n    div((nuEff*dev(T(grad(U))))) Gauss linear;\n}\n\n'
        ofheader += 'laplacianSchemes\n{\n    default         Gauss linear corrected;\n}\n\n' + \
        'interpolationSchemes\n{\n    default         linear;\n}\n\nsnGradSchemes\n{\n    default         corrected;\n}\n\n' + \
        'fluxRequired\n{\n    default         no;\n    p               ;\n}\n'
    return ofheader

def fvtppwrite(solver):
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    location    "constant";\n    object      transportProperties;\n}\n\n'
    if solver == 'icoFoam':
        return ofheader + 'nu              nu [ 0 2 -1 0 0 0 0 ] 0.01;\n'
    else:
        return ofheader + 'transportModel  Newtonian;\n\nrho             rho [ 1 -3 0 0 0 0 0 ] 1;\n\nnu              nu [ 0 2 -1 0 0 0 0 ] 1e-05;\n\n' + \
        'CrossPowerLawCoeffs\n{\n    nu0             nu0 [ 0 2 -1 0 0 0 0 ] 1e-06;\n    nuInf           nuInf [ 0 2 -1 0 0 0 0 ] 1e-06;\n    m               m [ 0 0 1 0 0 0 0 ] 1;\n' + \
        '    n               n [ 0 0 0 0 0 0 0 ] 1;\n}\n\n' + \
        'BirdCarreauCoeffs\n{\n    nu0             nu0 [ 0 2 -1 0 0 0 0 ] 1e-06;\n    nuInf           nuInf [ 0 2 -1 0 0 0 0 ] 1e-06;\n' + \
        '    k               k [ 0 0 1 0 0 0 0 ] 0;\n    n               n [ 0 0 0 0 0 0 0 ] 1;\n}'
        
def fvraswrite(turb):
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    location    "constant";\n    object      RASProperties;\n}\n\n'
    return ofheader + 'RASModel        {};\n\nturbulence      on;\n\nprintCoeffs     on;\n'.format(turb)
    
def fvshmwrite(node, o, **kwargs):    
    layersurf = '({}|{})'.format(kwargs['ground'][0].name, o.name) if kwargs and kwargs['ground'] else o.name 
    ofheader = 'FoamFile\n{\n    version     2.0;\n    format      ascii;\n    class       dictionary;\n    object      snappyHexMeshDict;\n}\n\n'
    ofheader += 'castellatedMesh    {};\nsnap    {};\naddLayers    {};\ndebug    {};\n\n'.format('true', 'true', 'true', 0)
    ofheader += 'geometry\n{{\n    {0}.obj\n    {{\n        type triSurfaceMesh;\n        name {0};\n    }}\n}};\n\n'.format(o.name)
    ofheader += 'castellatedMeshControls\n{{\n  maxLocalCells {};\n  maxGlobalCells {};\n  minRefinementCells {};\n  maxLoadUnbalance 0.10;\n  nCellsBetweenLevels {};\n'.format(node.lcells, node.gcells, int(node.gcells/100), node.ncellsbl)
    ofheader += '  features\n  (\n    {{\n      file "{}.eMesh";\n      level {};\n    }}\n  );\n\n'.format(o.name, node.level)
    ofheader += '  refinementSurfaces\n  {{\n    {}\n    {{\n      level ({} {});\n    }}\n  }}\n\n  '.format(o.name, node.surflmin, node.surflmax) 
    ofheader += '  resolveFeatureAngle 30;\n  refinementRegions\n  {}\n\n'
    ofheader += '  locationInMesh ({} {} {});\n  allowFreeStandingZoneFaces true;\n}}\n\n'.format(0.1, 0.1, 0.1)
    ofheader += 'snapControls\n{\n  nSmoothPatch 3;\n  tolerance 2.0;\n  nSolveIter 30;\n  nRelaxIter 5;\n  nFeatureSnapIter 10;\n  implicitFeatureSnap false;\n  explicitFeatureSnap true;\n  multiRegionFeatureSnap false;\n}\n\n'
    ofheader += 'addLayersControls\n{{\n  relativeSizes true;\n  layers\n  {{\n    "{}.*"\n    {{\n      nSurfaceLayers {};\n    }}\n  }}\n\n'.format(layersurf, node.layers)
    ofheader += '  expansionRatio 1.0;\n  finalLayerThickness 0.3;\n  minThickness 0.1;\n  nGrow 0;\n  featureAngle 60;\n  slipFeatureAngle 30;\n  nRelaxIter 3;\n  nSmoothSurfaceNormals 1;\n  nSmoothNormals 3;\n' + \
                '  nSmoothThickness 10;\n  maxFaceThicknessRatio 0.5;\n  maxThicknessToMedialRatio 0.3;\n  minMedianAxisAngle 90;\n  nBufferCellsNoExtrude 0;\n  nLayerIter 50;\n}\n\n'
    ofheader += 'meshQualityControls\n{\n  #include "meshQualityDict"\n  nSmoothScale 4;\n  errorReduction 0.75;\n}\n\n'
    ofheader += 'writeFlags\n(\n  scalarLevels\n  layerSets\n  layerFields\n);\n\nmergeTolerance 1e-6;\n'
    return ofheader

def fvmqwrite():
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      meshQualityDict;\n}\n\n'
    ofheader += '#include "$WM_PROJECT_DIR/etc/caseDicts/meshQualityDict"'
    return ofheader
    
def fvsfewrite(oname):
    ofheader = 'FoamFile\n{\n  version     2.0;\n  format      ascii;\n  class       dictionary;\n  object      surfaceFeatureExtractDict;\n}\n\n'
    ofheader += '{}.obj\n{{\n  extractionMethod    extractFromSurface;\n\n  extractFromSurfaceCoeffs\n  {{\n    includedAngle   150;\n  }}\n\n    writeObj\n    yes;\n}}\n'.format(oname)
    return ofheader

def fvobjwrite(scene, o, bmo):
    objheader = '# FloVi obj exporter\no {}\n'.format(o.name)
    objheader = '# FloVi obj exporter\n'
    bmomw, bmovs = bmo.matrix_world, [vert for vert in bmo.data.vertices]
    omw, ovs = o.matrix_world, [vert for vert in o.data.vertices]
    xvec, yvec, zvec = (bmomw*bmovs[3].co - bmomw*bmovs[0].co).normalized(), (bmomw*bmovs[2].co - bmomw*bmovs[3].co).normalized(), (bmomw*bmovs[4].co - bmomw*bmovs[0].co).normalized() 
    ofvpos = [[(omw*ov.co - bmomw*bmovs[0].co)*vec for vec in (xvec, yvec, zvec)] for ov in ovs]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    vcos = ''.join(['v {} {} {}\n'.format(*ofvpo) for ofvpo in ofvpos])
    with open(os.path.join(scene['flparams']['ofctsfilebase'], '{}.obj'.format(o.name)), 'w') as objfile:
        objfile.write(objheader+vcos)
        for m, mat in enumerate(o.data.materials):
            objfile.write('g {}\n'.format(mat.name) + ''.join(['f {} {} {}\n'.format(*[v.index + 1 for v in f.verts]) for f in bmesh.ops.triangulate(bm, faces = bm.faces)['faces'] if f.material_index == m]))
        objfile.write('#{}'.format(len(bm.faces)))
    bm.free()
    
def sunposenvi(scene, sun, dirsol, difsol, mdata, ddata, hdata):
    frames = range(scene.frame_start, scene.frame_end)
    times = [datetime.datetime(datetime.datetime.now().year, mdata[hi], ddata[hi], h - 1, 0) for hi, h in enumerate(hdata)]
    solposs = [solarPosition(time.timetuple()[7], time.hour + (time.minute)*0.016666, scene.latitude, scene.longitude) for time in times]
    beamvals = [0.01 * d for d in dirsol]
    skyvals =  [1 + 0.01 * d for d in difsol]
    sizevals = [beamvals[t]/skyvals[t] for t in range(len(times))]
    values = list(zip(sizevals, beamvals, skyvals))
    sunapply(scene, sun, values, solposs, frames)

def hdrsky(hdrfile):
    return("# Sky material\nvoid colorpict hdr_env\n7 red green blue {} angmap.cal sb_u sb_v\n0\n0\n\nhdr_env glow env_glow\n0\n0\n4 1 1 1 0\n\nenv_glow bubble sky\n0\n0\n4 0 0 0 5000\n\n".format(hdrfile))
       
def sunposlivi(scene, skynode, frames, sun, stime):
    sun.data.shadow_method, sun.data.shadow_ray_samples, sun.data.sky.use_sky = 'RAY_SHADOW', 8, 1
    if skynode['skynum'] < 3: 
        times = [stime + frame*datetime.timedelta(seconds = 3600*skynode.interval) for frame in range(len(frames))]  
        solposs = [solarPosition(time.timetuple()[7], time.hour + (time.minute)*0.016666, scene.latitude, scene.longitude) for time in times]
        beamvals = [solposs[t][0]/15 for t in range(len(times))] if skynode['skynum'] < 2 else [0 for t in range(len(times))]
        skyvals = beamvals
    elif skynode['skynum'] == 3: 
        times = [datetime.datetime(datetime.datetime.now().year, 3, 20, 12, 0)]
        solposs = [solarPosition(time.timetuple()[7], time.hour + (time.minute)*0.016666, 0, 0) for time in times]
        beamvals = [0 for t in range(len(times))]
        skyvals = [5 for t in range(len(times))]
    shaddict = {'0': 0.01, '1': 2, '2': 5, '3': 5}
    values = list(zip([shaddict[str(skynode['skynum'])] for t in range(len(times))], beamvals, skyvals))
    sunapply(scene, sun, values, solposs, frames)

def sunapply(scene, sun, values, solposs, frames):
    sun.data.animation_data_clear()
    sun.animation_data_clear()
    sun.animation_data_create()
    sun.animation_data.action = bpy.data.actions.new(name="EnVi Sun")
    sunposx = sun.animation_data.action.fcurves.new(data_path="location", index = 0)
    sunposy = sun.animation_data.action.fcurves.new(data_path="location", index = 1)
    sunposz = sun.animation_data.action.fcurves.new(data_path="location", index = 2)
    sunposx.keyframe_points.add(len(frames))
    sunposy.keyframe_points.add(len(frames))
    sunposz.keyframe_points.add(len(frames))
    sunrotx = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 0)
    sunroty = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 1)
    sunrotz = sun.animation_data.action.fcurves.new(data_path="rotation_euler", index = 2)
    sunrotx.keyframe_points.add(len(frames))
    sunroty.keyframe_points.add(len(frames))
    sunrotz.keyframe_points.add(len(frames))
    sunenergy = sun.animation_data.action.fcurves.new(data_path="energy")
    sunenergy.keyframe_points.add(len(frames))
    
# This is an attempt to use low level routines for node value animation but it don't work.
    if sun.data.node_tree:
        sun.data.node_tree.animation_data_clear()
        sun.data.node_tree.animation_data_create()
        sun.data.node_tree.animation_data.action = bpy.data.actions.new(name="EnVi Sun Node")
        emnodes = [emnode for emnode in sun.data.node_tree.nodes if emnode.bl_label == 'Emission']
        for emnode in emnodes:
            em1 = sun.data.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[0].default_value'.format(emnode.name), index = 2)
            em2 = sun.data.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[1].default_value'.format(emnode.name))
            em1.keyframe_points.add(len(frames))
            em2.keyframe_points.add(len(frames))
    
    if scene.world.node_tree:
        scene.world.node_tree.animation_data_clear() 
        scene.world.node_tree.animation_data_create()
        scene.world.node_tree.animation_data.action = bpy.data.actions.new(name="EnVi World Node") 
        stnodes = [stnode for stnode in scene.world.node_tree.nodes if stnode.bl_label == 'Sky Texture']
        bnodes = [bnode for bnode in scene.world.node_tree.nodes if bnode.bl_label == 'Background']
        for stnode in stnodes:
            st1x = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 0)
            st1y = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 1)
            st1z = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].sun_direction'.format(stnode.name), index = 2)
            st1x.keyframe_points.add(len(frames))
            st1y.keyframe_points.add(len(frames))
            st1z.keyframe_points.add(len(frames))
        for bnode in bnodes:
            b1 = scene.world.node_tree.animation_data.action.fcurves.new(data_path='nodes["{}"].inputs[1].default_value'.format(bnode.name))
            b1.keyframe_points.add(len(frames))

    for f, frame in enumerate(frames):
        (sun.data.shadow_soft_size, sun.data.energy) = values[f][:2]
        sunpos = [x*20 for x in (-sin(solposs[f][3]), -cos(solposs[f][3]), tan(solposs[f][2]))]
        sunrot = [(pi/2) - solposs[f][2], 0, -solposs[f][3]]
        if scene.render.engine == 'CYCLES' and scene.world.node_tree:
            if 'Sky Texture' in [no.bl_label for no in scene.world.node_tree.nodes]:
                skydir = -sin(solposs[f][3]), -cos(solposs[f][3]), sin(solposs[f][2])
                st1x.keyframe_points[f].co = frame, skydir[0]
                st1y.keyframe_points[f].co = frame, skydir[1]
                st1z.keyframe_points[f].co = frame, skydir[2]
            b1.keyframe_points[f].co = frame, values[f][2]

        if scene.render.engine == 'CYCLES' and sun.data.node_tree:
            for emnode in [emnode for emnode in sun.data.node_tree.nodes if emnode.bl_label == 'Emission']:
                em1.keyframe_points[f].co = frame, values[f][1]
                em2.keyframe_points[f].co = frame, values[f][1]
                   
        sunposx.keyframe_points[f].co = frame, sunpos[0]
        sunposy.keyframe_points[f].co = frame, sunpos[1]
        sunposz.keyframe_points[f].co = frame, sunpos[2]
        sunrotx.keyframe_points[f].co = frame, sunrot[0]
        sunroty.keyframe_points[f].co = frame, sunrot[1]
        sunrotz.keyframe_points[f].co = frame, sunrot[2]
        sunenergy.keyframe_points[f].co = frame, values[f][1]

    sun.data.cycles.use_multiple_importance_sampling = True
