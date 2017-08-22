# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "VI-Suite",
    "author": "Ryan Southall",
    "version": (0, 4, 12),
    "blender": (2, 7, 8),
    "api": "",
    "location": "Node Editor & 3D View > Properties Panel",
    "description": "Radiance/EnergyPlus exporter and results visualiser",
    "warning": "This is a beta script. Some functionality is buggy",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}

if "bpy" in locals():
    import imp
    imp.reload(vi_node)
    imp.reload(vi_operators)
    imp.reload(vi_ui)
    imp.reload(vi_func)
    imp.reload(envi_mat)
else:
    from .vi_node import vinode_categories, envinode_categories
    from . import envi_mat
    from .vi_func import iprop, bprop, eprop, fprop, sprop, fvprop, sunpath1, fvmat, radmat, radbsdf, retsv, cmap
    from .vi_func import rtpoints, lhcalcapply, udidacalcapply, compcalcapply, basiccalcapply, lividisplay, setscenelivivals
    from .envi_func import enunits, enpunits, enparametric, resnameunits, aresnameunits
    from .vi_display import setcols
    from .vi_operators import *
    from .vi_ui import *

import sys, os, inspect, bpy, nodeitems_utils, bmesh, math, mathutils
from bpy.app.handlers import persistent
from numpy import array, digitize, logspace, multiply
from numpy import log10 as nlog10

from bpy.props import (
    StringProperty, EnumProperty, IntProperty,
    CollectionProperty, PointerProperty
    )
from bpy.types import (
    AddonPreferences, PropertyGroup,
    Object, Scene, Material
    )

class VIPreferences(AddonPreferences):
    bl_idname=__name__

    radbin = StringProperty(name='', description = 'Radiance binary directory location', default = '', subtype='DIR_PATH')
    radlib = StringProperty(name='', description = 'Radiance library directory location', default = '', subtype='DIR_PATH')
    epbin = StringProperty(name='', description = 'EnergyPlus binary directory location', default = '', subtype='DIR_PATH')
    epweath = StringProperty(name='', description = 'EnergyPlus weather directory location', default = '', subtype='DIR_PATH')

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Radiance bin directory:")
        row.prop(self, 'radbin')
        row = layout.row()
        row.label(text="Radiance lib directory:")
        row.prop(self, 'radlib')
        row = layout.row()
        row.label(text="EnergyPlus bin directory:")
        row.prop(self, 'epbin')
        row = layout.row()
        row.label(text="EnergyPlus weather directory:")
        row.prop(self, 'epweath')

@persistent
def update_chart_node(dummy):
    try:
        for ng in [ng for ng in bpy.data.node_groups if ng.bl_idname == 'ViN']:
            [node.update() for node in ng.nodes if node.bl_label == 'VI Chart']
    except Exception as e:
        print('Chart node update failure:', e)

@persistent
def update_dir(dummy):
    if bpy.context.scene.get('viparams'):
        fp = bpy.data.filepath
        bpy.context.scene['viparams']['newdir'] = os.path.join(os.path.dirname(fp), os.path.splitext(os.path.basename(fp))[0])

@persistent
def display_off(dummy):
    if bpy.context.scene.get('viparams') and bpy.context.scene['viparams'].get('vidisp'):

        ifdict = {'sspanel': 'ss', 'lipanel': 'li', 'enpanel': 'en', 'bsdf_panel': 'bsdf'}
        if bpy.context.scene['viparams']['vidisp'] in ifdict:
            bpy.context.scene['viparams']['vidisp'] = ifdict[bpy.context.scene['viparams']['vidisp']]
        bpy.context.scene.vi_display = 0
@persistent
def mesh_index(dummy):
    try:
        cao = bpy.context.active_object

        if cao and cao.layers[1] and cao.mode == 'EDIT':
            if not bpy.app.debug:
                bpy.app.debug = True
        elif bpy.app.debug:
            bpy.app.debug = False
    except:
        pass

@persistent
def select_nodetree(dummy):
    for space in getViEditorSpaces():
        vings = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'ViN']
        if vings:
            space.node_tree = vings[0]
    for space in getEnViEditorSpaces():
        envings = [ng for ng in bpy.data.node_groups if ng.bl_idname == 'EnViN']
        if envings:
            space.node_tree = envings[0]

def getViEditorSpaces():
    if bpy.context.screen:
        return [area.spaces.active for area in bpy.context.screen.areas if area and area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "ViN" and not area.spaces.active.edit_tree]
    else:
        return []

def getEnViEditorSpaces():
    if bpy.context.screen:
        return [area.spaces.active for area in bpy.context.screen.areas if area and area.type == "NODE_EDITOR" and area.spaces.active.tree_type == "EnViN" and not area.spaces.active.edit_tree]
    else:
        return []

bpy.app.handlers.scene_update_post.append(select_nodetree)
bpy.app.handlers.scene_update_post.append(mesh_index)

epversion = "8-7-0"
addonpath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
matpath, epwpath, envi_mats, envi_cons, conlayers  = addonpath+'/EPFiles/Materials/Materials.data', addonpath+'/EPFiles/Weather/', envi_materials(), envi_constructions(), 5
evsep = {'linux': ':', 'darwin': ':', 'win32': ';'}
vi_prefs = bpy.context.user_preferences.addons[__name__].preferences
radldir = bpy.path.abspath(vi_prefs.radlib) if vi_prefs and os.path.isdir(bpy.path.abspath(vi_prefs.radlib)) else os.path.join('{}'.format(addonpath), 'Radfiles', 'lib')
radbdir = bpy.path.abspath(vi_prefs.radbin) if vi_prefs and os.path.isdir(bpy.path.abspath(vi_prefs.radbin)) else os.path.join('{}'.format(addonpath), 'Radfiles', 'bin')
epdir = bpy.path.abspath(vi_prefs.epbin) if vi_prefs and os.path.isdir(bpy.path.abspath(vi_prefs.epbin)) else os.path.join('{}'.format(addonpath), 'EPFiles', 'bin')
os.environ["PATH"] += "{0}{1}".format(evsep[str(sys.platform)], os.path.dirname(bpy.app.binary_path))

if not os.environ.get('RAYPATH') or radldir not in os.environ['RAYPATH'] or radbdir not in os.environ['PATH']  or epdir not in os.environ['PATH']:
    if vi_prefs and os.path.isdir(vi_prefs.radlib):
        os.environ["RAYPATH"] = '{0}{1}{2}'.format(radldir, evsep[str(sys.platform)], os.path.join(addonpath, 'Radfiles', 'lib'))
    else:
        os.environ["RAYPATH"] = radldir

    os.environ["PATH"] = os.environ["PATH"] + "{0}{1}{0}{2}".format(evsep[str(sys.platform)], radbdir, epdir)

def colupdate(self, context):
    cmap(self)

"""
def confunc(i):
    confuncdict = {'0': envi_cons.wall_con.keys(), '1': envi_cons.floor_con.keys(), '2': envi_cons.roof_con.keys(),
    '3': envi_cons.door_con.keys(), '4': envi_cons.glaze_con.keys()}
    return [((con, con, 'Contruction type')) for con in list(confuncdict[str(i)])]

(wallconlist, floorconlist, roofconlist, doorconlist, glazeconlist) = [confunc(i) for i in range(5)]
"""

def eupdate(self, context):
    scene = context.scene
    maxo, mino = scene.vi_leg_max, scene.vi_leg_min
    odiff = scene.vi_leg_max - scene.vi_leg_min

    if context.active_object.mode == 'EDIT':
        return
    if odiff:
        for frame in range(scene['liparams']['fs'], scene['liparams']['fe'] + 1):
            for o in [obj for obj in bpy.data.objects if obj.lires == 1 and obj.data.shape_keys and str(frame) in [sk.name for sk in obj.data.shape_keys.key_blocks]]:
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.transform(o.matrix_world)
                skb = bm.verts.layers.shape['Basis']
                skf = bm.verts.layers.shape[str(frame)]

                if str(frame) in o['omax']:
                    if bm.faces.layers.float.get('res{}'.format(frame)):
                        extrude = bm.faces.layers.int['extrude']
                        res = bm.faces.layers.float['res{}'.format(frame)] #if context.scene['cp'] == '0' else bm.verts.layers.float['res{}'.format(frame)]
                        faces = [f for f in bm.faces if f[extrude]]
                        fnorms = array([f.normal.normalized() for f in faces]).T
                        fres = array([f[res] for f in faces])
                        extrudes = (0.1 * scene.vi_disp_3dlevel * (nlog10(maxo * (fres + 1 - mino)/odiff)) * fnorms).T if scene.vi_leg_scale == '1' else \
                            multiply(fnorms, scene.vi_disp_3dlevel * ((fres - mino)/odiff)).T

                        for f, face in enumerate(faces):
                            for v in face.verts:
                                v[skf] = v[skb] + mathutils.Vector(extrudes[f])

                    elif bm.verts.layers.float.get('res{}'.format(frame)):
                        res = bm.verts.layers.float['res{}'.format(frame)]
                        vnorms = array([v.normal.normalized() for v in bm.verts]).T
                        vres = array([v[res] for v in bm.verts])
                        extrudes = multiply(vnorms, scene.vi_disp_3dlevel * ((vres-mino)/odiff)).T if scene.vi_leg_scale == '0' else \
                            [0.1 * scene.vi_disp_3dlevel * (math.log10(maxo * (v[res] + 1 - mino)/odiff)) * v.normal.normalized() for v in bm.verts]
                        for v, vert in enumerate(bm.verts):
                            vert[skf] = vert[skb] + mathutils.Vector(extrudes[v])

                bm.transform(o.matrix_world.inverted())
                bm.to_mesh(o.data)
                bm.free()

def tupdate(self, context):
    for o in [o for o in context.scene.objects if o.type == 'MESH'  and 'lightarray' not in o.name and o.hide == False and o.layers[context.scene.active_layer] == True and o.get('lires')]:
        o.show_transparent = 1
    for mat in [bpy.data.materials['{}#{}'.format('vi-suite', index)] for index in range(20)]:
        mat.use_transparency, mat.transparency_method, mat.alpha = 1, 'MASK', context.scene.vi_disp_trans

def wupdate(self, context):
    o = context.active_object
    if o and o.type == 'MESH':
        (o.show_wire, o.show_all_edges) = (1, 1) if context.scene.vi_disp_wire else (0, 0)

def legupdate(self, context):
    scene = context.scene
    frames = range(scene['liparams']['fs'], scene['liparams']['fe'] + 1)
    obs = [o for o in scene.objects if o.get('lires')]

    if scene.vi_leg_scale == '0':
        bins = array([0.05 * i for i in range(1, 20)])
    elif scene.vi_leg_scale == '1':
        slices = logspace(0, 2, 21, True)
        bins = array([(slices[i] - 0.05 * (20 - i))/100 for i in range(21)])
        bins = array([1 - math.log10(i)/math.log10(21) for i in range(1, 22)][::-1])
        bins = bins[1:-1]

    for o in obs:
        bm = bmesh.new()
        bm.from_mesh(o.data)

        for f, frame in enumerate(frames):
            if bm.faces.layers.float.get('res{}'.format(frame)):
                livires = bm.faces.layers.float['res{}'.format(frame)]
                ovals = array([f[livires] for f in bm.faces])
            elif bm.verts.layers.float.get('res{}'.format(frame)):
                livires = bm.verts.layers.float['res{}'.format(frame)]
                ovals = array([sum([vert[livires] for vert in f.verts])/len(f.verts) for f in bm.faces])

            if scene.vi_leg_max > scene.vi_leg_min:
                vals = ovals - scene.vi_leg_min
                vals = vals/(scene.vi_leg_max - scene.vi_leg_min)
            else:
                print('All result values are the same')
                vals = array([scene.vi_leg_max for f in bm.faces])

            nmatis = digitize(vals, bins)

            if len(frames) == 1:
                o.data.polygons.foreach_set('material_index', nmatis)
                o.data.update()

            elif len(frames) > 1:
                for fi, fc in enumerate(o.data.animation_data.action.fcurves):
                    fc.keyframe_points[f].co = frame, nmatis[fi]
        bm.free()
    scene.frame_set(scene.frame_current)

def liviresupdate(self, context):
    setscenelivivals(context.scene)
    for o in [o for o in bpy.data.objects if o.lires]:
        o.lividisplay(context.scene)
    eupdate(self, context)


class VISUITE_Object_Livi(PropertyGroup):
    # LiVi object properties
    livi_merr = bprop("LiVi simple mesh export", "Boolean for simple mesh export", False)
    ies_name=sprop("", "IES File", 1024, "")
    ies_strength = fprop("", "Strength of IES lamp", 0, 1, 1)
    ies_unit = eprop([("m", "Meters", ""), 
        ("c", "Centimeters", ""), 
        ("f", "Feet", ""), 
        ("i", "Inches", "")], 
        "", 
        "Specify the IES file measurement unit", "m")
    ies_colmenu = eprop([("0", "RGB", ""), 
        ("1", "Temperature", "")], 
        "", 
        "Specify the IES colour type", "0")
    ies_rgb = fvprop(3, "",'IES Colour', [1.0, 1.0, 1.0], 'COLOR', 0, 1)
    ies_ct = iprop("", "Colour temperature in Kelven", 0, 12000, 4700)
    (licalc, lires, limerr, manip, bsdf_proxy) = [bprop("", "", False)] * 5
    compcalcapply = compcalcapply
    basiccalcapply = basiccalcapply
    rtpoints = rtpoints
    udidacalcapply = udidacalcapply
    lividisplay = lividisplay
    lhcalcapply = lhcalcapply
    li_bsdf_direc = EnumProperty(
        items=[('+b -f', 'Backwards', 'Backwards BSDF'), 
            ('+f -b', 'Forwards', 'Forwards BSDF'), 
            ('+b +f', 'Bi-directional', 'Bi-directional BSDF')], 
        name='', 
        description='BSDF direction', 
        default='+b -f')
    li_bsdf_tensor = EnumProperty(
        items=[(' ', 'Klems', 'Uniform Klems sample'), 
            ('-t3', 'Symmentric', 'Symmetric Tensor BSDF'), 
            ('-t4', 'Assymmetric', 'Asymmetric Tensor BSDF')], 
        name='', 
        description='BSDF tensor', 
        default=' ')
    li_bsdf_res = EnumProperty(
        items=[('1', '2x2', '2x2 sampling resolution'), 
            ('2', '4x4', '4x4 sampling resolution'), 
            ('3', '8x8', '8x8 sampling resolution'), 
            ('4', '16x16', '16x16 sampling resolution'), 
            ('5', '32x32', '32x32 sampling resolution'), 
            ('6', '64x64', '64x64 sampling resolution'), 
            ('7', '128x128', '128x128 sampling resolution')], 
        name='', 
        description='BSDF resolution', 
        default='4')
    li_bsdf_tsamp = IntProperty(name='', description='Tensor samples', min=1, max=20, default=4)
    li_bsdf_ksamp = IntProperty(name='', description='Klem samples', min=1, default=200)
    li_bsdf_rcparam = sprop("", "rcontrib parameters", 1024, "")
    li_bsdf_proxy_depth = fprop("", "Depth of proxy geometry", -10, 10, 0)
    radbsdf = radbsdf
    retsv = retsv


# Livi enums
radtypes = [('0', 'Plastic', 'Plastic Radiance material'),
            ('1', 'Glass', 'Glass Radiance material'),
            ('2', 'Dielectric', 'Dialectric Radiance material'),
            ('3', 'Translucent', 'Translucent Radiance material'),
            ('4', 'Mirror', 'Mirror Radiance material'),
            ('5', 'Light', 'Emission Radiance material'),
            ('6', 'Metal', 'Metal Radiance material'),
            ('7', 'Anti-matter', 'Antimatter Radiance material'),
            ('8', 'BSDF', 'BSDF Radiance material'),
            ('9', 'Custom', 'Custom Radiance material')]

hspacetype = [('0', 'Public/Staff', 'Public/Staff area'),
              ('1', 'Patient', 'Patient area')]

rspacetype = [('0', "Kitchen", "Kitchen space"),
              ('1', "Living/Dining/Study", "Living/Dining/Study area"),
              ('2', "Communal", "Non-residential or communal area")]

respacetype = [('0', "Sales", "Sales space"),
               ('1', "Occupied", "Occupied space")]

lespacetype = [('0', "Healthcare", "Healthcare space"),
               ('1', "Other", "Other space")]

               
class VISUITE_Material_Livi(PropertyGroup):
    radmat = radmat
    radmatdict = {'0': ['radcolour', 0, 'radrough', 'radspec'], '1': ['radcolour'], '2': ['radcolour', 0, 'radior'], '3': ['radcolour', 0, 'radspec', 'radrough', 0, 'radtrans',  'radtranspec'], '4': ['radcolour'],
    '5': ['radcolmenu', 0, 'radcolour', 0, 'radct',  0, 'radintensity'], '6': ['radcolour', 0, 'radrough', 'radspec'], '7': [], '8': [], '9': []}
    pport = bprop("", "Flag to signify whether the material represents a Photon Port", False)
    radtex = bprop("", "Flag to signify whether the material has a texture associated with it", False)
    radnorm = bprop("", "Flag to signify whether the material has a normal map associated with it", False)
    ns = fprop("", "Strength of normal effect", 0, 5, 1)
    nu = fvprop(3, '', 'Image up vector', [0, 0, 1], 'VELOCITY', -1, 1)
    nside = fvprop(3, '', 'Image side vector', [-1, 0, 0], 'VELOCITY', -1, 1)
#   gup = eprop([("0", "Up", "Green channel is up"), ("1", "Down", "Green channel is down")], "", "Specify the direction of the green channel", "0")
    radmatmenu = eprop(radtypes, "", "Type of Radiance material", '0')
    radcolour = fvprop(3, "Material Colour",'Material Colour', [0.8, 0.8, 0.8], 'COLOR', 0, 1)
    radcolmenu = eprop([("0", "RGB", "Specify colour temperature"), ("1", "Temperature", "Specify colour temperature")], "Colour type:", "Specify the colour input", "0")
    radrough = fprop("Roughness", "Material roughness", 0, 1, 0.1)
    radspec = fprop("Specularity", "Material specularity", 0, 1, 0.0)
    radtrans = fprop("Transmission", "Material transmissivity", 0, 1, 0.1)
    radtranspec  = fprop("Trans spec", "Material specular transmission", 0, 1, 0.1)
    radior  = fprop("IOR", "Material index of refractionn", 0, 5, 1.5)
    radct = iprop("Temperature (K)", "Colour temperature in Kelven", 0, 12000, 4700)
    radintensity = fprop("Intensity", u"Material radiance (W/sr/m\u00b2)", 0, 100, 1)
    radfile = sprop("", "Radiance file material description", 1024, "")
    vi_shadow = bprop("VI Shadow", "Flag to signify whether the material represents a VI Shadow sensing surface", False)
    livi_sense = bprop("LiVi Sensor", "Flag to signify whether the material represents a LiVi sensing surface", False)
    livi_compliance = bprop("LiVi Compliance Surface", "Flag to siginify whether the material represents a LiVi compliance surface", False)
    gl_roof = bprop("Glazed Roof", "Flag to siginify whether the communal area has a glazed roof", False)
    hspacemenu = eprop(hspacetype, "", "Type of healthcare space", '0')
    brspacemenu = eprop(rspacetype, "", "Type of residential space", '0')
    crspacemenu = eprop(rspacetype[:2], "", "Type of residential space", '0')
    respacemenu = eprop(respacetype, "", "Type of retail space", '0')
    lespacemenu = eprop(lespacetype, "", "Type of space", '0')
    BSDF = bprop("", "Flag to signify a BSDF material", False)


def register():
    bpy.utils.register_module(__name__)
    Object, Scene, Material = bpy.types.Object, bpy.types.Scene, bpy.types.Material

# VI-Suite object definitions
    Object.visuite_type = eprop([
            ("0", "None", "Not a VI-Suite zone"),
            # ("1", "EnVi Zone", "Designates an EnVi Thermal zone"),
            ("2", "CFD Domain", "Specifies an OpenFoam BlockMesh"),
            ("3", "CFD Geometry", "Specifies an OpenFoam geometry"),
            ("4", "Light Array", "Specifies a LiVi lighting array"),
            ("5", "Complex Fenestration", "Specifies complex fenestration for BSDF generation")],
            "", "Specify the type of VI-Suite zone", "0")

# LiVi object properties
    Object.visuite_livi = PointerProperty(type=VISUITE_Object_Livi)

# EnVi zone definitions
    # Object.visuite_envi = PointerProperty(type=VISUITE_Object_Envi)

# FloVi object definitions

# Vi_suite material definitions
    Material.visuite_mattype = eprop([
        ("0", "Geometry", "Geometry"),
        ("1", 'Light sensor', "LiVi sensing material".format(u'\u00b3')),
        ("2", "FloVi boundary", 'FloVi blockmesh boundary')],
        "", "VI-Suite material type", "0")

# LiVi material definitions
    Material.visuite_livi = PointerProperty(type=VISUITE_Material_Livi)

# EnVi material definitions
    # Material.visuite_envi = CollectionProperty(type=VISUITE_Material_Envi)


# FloVi material definitions
    Material.fvmat = fvmat
    Material.flovi_bmb_type = eprop([("0", "Wall", "Wall boundary"), ("1", "Inlet", "Inlet boundary"), ("2", "Outlet", "Outlet boundary"), ("3", "Symmetry", "Symmetry boundary"), ("4", "Empty", "Empty boundary")], "", "FloVi blockmesh boundary type", "0")
    Material.flovi_bmwp_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
    Material.flovi_bmwu_type = eprop([("fixedValue", "Fixed", "Fixed value boundary"), ("slip", "Slip", "Slip boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmwnutilda_type = eprop([("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmwnut_type = eprop([("nutUSpaldingWallFunction", "SpaldingWF", "Fixed value boundary"), ("nutkWallFunction", "k wall function", "Fixed value boundary")], "", "FloVi wall boundary type", "nutUSpaldingWallFunction")
    Material.flovi_bmwk_type = eprop([("kqRWallFunction", "kqRWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "kqRWallFunction")
    Material.flovi_bmwe_type = eprop([("epsilonWallFunction", "epsilonWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "epsilonWallFunction")
    Material.flovi_bmwo_type = eprop([("omegaWallFunction", "omegaWallFunction", "Fixed value boundary")], "", "FloVi wall boundary type", "omegaWallFunction")

    Material.flovi_bmu_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
    Material.flovi_bmu_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
    Material.flovi_bmu_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)

#    Material.flovi_bmwnut_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmwnut_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
    Material.flovi_bmip_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient pressure boundary"), ("freestreamPressure", "Freestream Pressure", "Free stream pressure gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
    Material.flovi_bmiop_val = fprop("X", "Pressure value", -1000, 1000, 0.0)
    Material.flovi_bmop_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient pressure boundary"), ("freestreamPressure", "Freestream Pressure", "Free stream pressure gradient boundary"), ("fixedValue", "FixedValue", "Fixed value pressure boundary")], "", "FloVi wall boundary type", "zeroGradient")
    Material.flovi_bmiu_type = eprop([("freestream", "Freestream velocity", "Freestream velocity boundary"), ("fixedValue", "Fixed Value", "Fixed velocity boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmou_type = eprop([("freestream", "Freestream velocity", "Freestream velocity boundary"), ("zeroGradient", "Zero Gradient", "Zero gradient  boundary"), ("fixedValue", "Fixed Value", "Fixed velocity boundary")], "", "FloVi wall boundary type", "zeroGradient")
    Material.flovi_bminut_type = eprop([("calculated", "Calculated", "Calculated value boundary")], "", "FloVi wall boundary type", "calculated")
    Material.flovi_bmonut_type = eprop([("calculated", "Calculated", "Calculated value boundary")], "", "FloVi wall boundary type", "calculated")
    Material.flovi_bminutilda_type = eprop([("freeStream", "Freestream", "Free stream value boundary")], "", "FloVi wall boundary type", "freeStream")
    Material.flovi_bmonutilda_type = eprop([("freeStream", "Freestream", "Free stream value boundary")], "", "FloVi wall boundary type", "freeStream")
    Material.flovi_bmik_type = eprop([("fixedValue", "Fixed Value", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmok_type = eprop([("inletOutlet", "Inlet/outlet", "Inlet/outlet boundary")], "", "FloVi wall boundary type", "inletOutlet")
    Material.flovi_bmie_type = eprop([("fixedValue", "Fixed Value", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmoe_type = eprop([("inletOutlet", "Inlet/outlet", "Inlet/outlet boundary")], "", "FloVi wall boundary type", "inletOutlet")
    Material.flovi_bmio_type = eprop([("zeroGradient", "Zero Gradient", "Zero gradient boundary")], "", "FloVi wall boundary type", "zeroGradient")
    Material.flovi_bmoo_type = eprop([("fixedValue", "Fixed", "Fixed value boundary")], "", "FloVi wall boundary type", "fixedValue")
    Material.flovi_bmiu_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
    Material.flovi_bmiu_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
    Material.flovi_bmiu_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
    Material.flovi_bmou_x = fprop("X", "Value in the X-direction", -1000, 1000, 0.0)
    Material.flovi_bmou_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
    Material.flovi_bmou_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)
    Material.flovi_bmnut = fprop("", "nuTilda value", -1000, 1000, 0.0)
    Material.flovi_bmk = fprop("", "k value", 0, 1000, 0.0)
    Material.flovi_bme = fprop("", "Epsilon value", 0, 1000, 0.0)
    Material.flovi_bmo = fprop("", "Omega value", 0, 1000, 0.0)
    Material.flovi_ground = bprop("", "Ground material", False)
    Material.flovi_b_sval = fprop("", "Scalar value", -500, 500, 0.0)
    Material.flovi_b_vval = fvprop(3, '', 'Vector value', [0, 0, 0], 'VELOCITY', -100, 100)
    Material.flovi_p_field = bprop("", "Take boundary velocity from the field velocity", False)
    Material.flovi_u_field = bprop("", "Take boundary velocity from the field velocity", False)

    
#    Material.flovi_bmionut = fprop("Value", "nuTilda value", -1000, 1000, 0.0)
#    Material.flovi_bmionut_y = fprop("Y", "Value in the Y-direction", -1000, 1000, 0.0)
#    Material.flovi_bmionut_z = fprop("Z", "Value in the Z-direction", -1000, 1000, 0.0)

# Scene parameters
    Scene.latitude = bpy.props.FloatProperty(name="Latitude", description = "Site Latitude", min = -89.99, max = 89.99, default = 52.0)
    Scene.longitude = bpy.props.FloatProperty(name="Longitude", description = "Site Longitude", min = -180, max = 180, default = 0.0)
    Scene.wind_type = eprop([("0", "Speed", "Wind Speed (m/s)"), ("1", "Direction", "Wind Direction (deg. from North)")], "", "Wind metric", "0")
    Scene.vipath = sprop("VI Path", "Path to files included with the VI-Suite ", 1024, addonpath)
    Scene.suns = EnumProperty(items=[('0', 'Single', 'Single sun'), ('1', 'Monthly', 'Monthly sun for chosen time'), ('2', 'Hourly', 'Hourly sun for chosen date')], name='', description = 'Sunpath sun type', default = '0', update=sunpath1)
    Scene.sunsstrength = bpy.props.FloatProperty(name="", description = "Sun strength", min = 0, max = 100, default = 0.1, update=sunpath1)
    Scene.sunssize = bpy.props.FloatProperty(name="", description = "Sun size", min = 0, max = 1, default = 0.01, update=sunpath1)
    Scene.solday = IntProperty(name="", description = "Day of year", min = 1, max = 365, default = 1, update=sunpath1)
    Scene.solhour = bpy.props.FloatProperty(name="", description = "Time of day", subtype='TIME', unit='TIME', min = 0, max = 24, default = 12, update=sunpath1)
    (Scene.hourdisp, Scene.spupdate, Scene.timedisp) = [bprop("", "",0)] * 3
    
    Scene.li_disp_panel = iprop("Display Panel", "Shows the Display Panel", -1, 2, 0)
    Scene.li_disp_count = iprop("", "", 0, 1000, 0)
    Scene.vi_disp_3d = bprop("VI 3D display", "Boolean for 3D results display",  False)
    Scene.vi_disp_3dlevel = bpy.props.FloatProperty(name="", description = "Level of 3D result plane extrusion", min = 0, max = 500, default = 0, update = eupdate)
    Scene.ss_disp_panel = iprop("Display Panel", "Shows the Display Panel", -1, 2, 0)
    
    (Scene.lic_disp_panel, Scene.vi_display, Scene.sp_disp_panel, 
        Scene.wr_disp_panel, Scene.ss_leg_display, Scene.en_disp_panel, 
        Scene.li_compliance, Scene.vi_display_rp, Scene.vi_leg_display,
        Scene.vi_display_sel_only, Scene.vi_display_vis_only) = [bprop("", "", False)] * 11
        
    Scene.vi_leg_max = bpy.props.FloatProperty(name="", description = "Legend maximum", min = 0, max = 1000000, default = 1000, update=legupdate)
    Scene.vi_leg_min = bpy.props.FloatProperty(name="", description = "Legend minimum", min = 0, max = 1000000, default = 0, update=legupdate)
    Scene.vi_scatter_max = bpy.props.FloatProperty(name="", description = "Scatter maximum", min = 0, max = 1000000, default = 1000, update=legupdate)
    Scene.vi_scatter_min = bpy.props.FloatProperty(name="", description = "Scatter minimum", min = 0, max = 1000000, default = 0, update=legupdate)
    Scene.vi_leg_scale = EnumProperty(items=[('0', 'Linear', 'Linear scale'), ('1', 'Log', 'Logarithmic scale')], name="", description = "Legend scale", default = '0', update=legupdate)
    Scene.vi_leg_col = EnumProperty(items=[('rainbow', 'Rainbow', 'Rainbow colour scale'), ('gray', 'Grey', 'Grey colour scale'), ('hot', 'Hot', 'Hot colour scale'),
                                             ('CMRmap', 'CMR', 'CMR colour scale'), ('jet', 'Jet', 'Jet colour scale'), ('plasma', 'Plasma', 'Plasma colour scale'), ('hsv', 'HSV', 'HSV colour scale'), ('viridis', 'Viridis', 'Viridis colour scale')], name="", description = "Legend scale", default = 'rainbow', update=colupdate)
    Scene.vi_bsdfleg_max = bpy.props.FloatProperty(name="", description = "Legend maximum", min = 0, max = 1000000, default = 100)
    Scene.vi_bsdfleg_min = bpy.props.FloatProperty(name="", description = "Legend minimum", min = 0, max = 1000000, default = 0)
    Scene.vi_bsdfleg_scale = EnumProperty(items=[('0', 'Linear', 'Linear scale'), ('1', 'Log', 'Logarithmic scale')], name="", description = "Legend scale", default = '0')
    
    Scene.gridifyup = fvprop(3, '', 'Grid up vector', [1, 0, 0], 'VELOCITY', -1, 1)
    Scene.gridifyus = fprop("", "Up direction size", 0.01, 10, 0.6)
    Scene.gridifyas = fprop("", "Side direction size", 0.01, 10, 0.6)

#    Scene.vi_lbsdf_direc = EnumProperty(items=bsdfdirec, name="", description = "Legend scale")

    Scene.en_disp = EnumProperty(items=[('0', 'Cylinder', 'Cylinder display'), ('1', 'Box', 'Box display')], name="", description = "Shape of EnVi result object", default = '0')
    Scene.en_disp_unit = EnumProperty(items=enunits, name="", description = "Type of EnVi metric display")
    Scene.en_disp_punit = EnumProperty(items=enpunits, name="", description = "Type of EnVi metric display")
    Scene.en_disp_type = EnumProperty(items=enparametric, name="", description = "Type of EnVi display")

    Scene.en_frame = iprop("", "EnVi frame", 0, 500, 0)
    Scene.en_temp_max = bpy.props.FloatProperty(name="Max", description = "Temp maximum", default = 24, update=setcols)
    Scene.en_temp_min = bpy.props.FloatProperty(name="Min", description = "Temp minimum", default = 18, update=setcols)
    Scene.en_hum_max = bpy.props.FloatProperty(name="Max", description = "Humidity maximum", default = 100, update=setcols)
    Scene.en_hum_min = bpy.props.FloatProperty(name="Min", description = "Humidity minimum", default = 0, update=setcols)
    Scene.en_heat_max = bpy.props.FloatProperty(name="Max", description = "Heating maximum", default = 1000, update=setcols)
    Scene.en_heat_min = bpy.props.FloatProperty(name="Min", description = "Heating minimum", default = 0, update=setcols)
    Scene.en_hrheat_max = bpy.props.FloatProperty(name="Max", description = "Heat recovery maximum", default = 1000, update=setcols)
    Scene.en_hrheat_min = bpy.props.FloatProperty(name="Min", description = "Heat recovery minimum", default = 0, update=setcols)
    Scene.en_aheat_max = bpy.props.FloatProperty(name="Max", description = "Air heating maximum", default = 1000, update=setcols)
    Scene.en_aheat_min = bpy.props.FloatProperty(name="Min", description = "Air heating minimum", default = 0, update=setcols)
    Scene.en_heatb_max = bpy.props.FloatProperty(name="Max", description = "Heat balance maximum", default = 1000, update=setcols)
    Scene.en_heatb_min = bpy.props.FloatProperty(name="Min", description = "Heat balance minimum", default = 0, update=setcols)
    Scene.en_cool_max = bpy.props.FloatProperty(name="Max", description = "Cooling maximum", default = 1000, update=setcols)
    Scene.en_cool_min = bpy.props.FloatProperty(name="Min", description = "Cooling minimum", default = 0, update=setcols)
    Scene.en_acool_max = bpy.props.FloatProperty(name="Max", description = "Air cooling maximum", default = 1000, update=setcols)
    Scene.en_acool_min = bpy.props.FloatProperty(name="Min", description = "Air cooling minimum", default = 0, update=setcols)
    Scene.en_co2_max = bpy.props.FloatProperty(name="Max", description = "CO2 maximum", default = 10000, update=setcols)
    Scene.en_co2_min = bpy.props.FloatProperty(name="Min", description = "CO2 minimum", default = 0, update=setcols)
    Scene.en_shg_max = bpy.props.FloatProperty(name="Max", description = "Solar heat gain maximum", min = 0, default = 10000, update=setcols)
    Scene.en_shg_min = bpy.props.FloatProperty(name="Min", description = "Solar heat gain minimum", min = 0, default = 0, update=setcols)
    Scene.en_ppd_max = bpy.props.FloatProperty(name="Max", description = "PPD maximum", default = 100, max = 100, min = 1, update=setcols)
    Scene.en_ppd_min = bpy.props.FloatProperty(name="Min", description = "PPD minimum", default = 0, max = 90, min = 0, update=setcols)
    Scene.en_pmv_max = bpy.props.FloatProperty(name="Max", description = "PMV maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_pmv_min = bpy.props.FloatProperty(name="Min", description = "PMV minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_occ_max = bpy.props.FloatProperty(name="Max", description = "Occupancy maximum", default = 3, min = 1, update=setcols)
    Scene.en_occ_min = bpy.props.FloatProperty(name="Min", description = "Occupancy minimum", default = 0, min = 0, update=setcols)
    Scene.en_iach_max = bpy.props.FloatProperty(name="Max", description = "Infiltration (ACH)  maximum", default = 2, min = 0.1, update=setcols)
    Scene.en_iach_min = bpy.props.FloatProperty(name="Min", description = "Infiltration (ACH) minimum", default = 0, min = 0, update=setcols)
    Scene.en_im3s_max = bpy.props.FloatProperty(name="Max", description = "Infiltration (m3/s)  maximum", default = 0.05, min = 0.01, update=setcols)
    Scene.en_im3s_min = bpy.props.FloatProperty(name="Min", description = "Infiltration (m3/s) minimum", default = 0, min = 0, update=setcols)
    Scene.en_maxheat_max = bpy.props.FloatProperty(name="Max", description = "Maximum heating maximum", default = 1000, max = 10000, min = 0, update=setcols)
    Scene.en_maxheat_min = bpy.props.FloatProperty(name="Min", description = "Maximum heating minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_aveheat_max = bpy.props.FloatProperty(name="Max", description = "Average heating maximum", default = 500, max = 10000, min = 0, update=setcols)
    Scene.en_aveheat_min = bpy.props.FloatProperty(name="Min", description = "Average heating minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_minheat_max = bpy.props.FloatProperty(name="Max", description = "Minimum heating maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_minheat_min = bpy.props.FloatProperty(name="Min", description = "Minimum heating minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_maxcool_max = bpy.props.FloatProperty(name="Max", description = "Maximum cooling maximum", default = 1000, max = 10000, min = 0, update=setcols)
    Scene.en_maxcool_min = bpy.props.FloatProperty(name="Min", description = "Maximum cooling minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_avecool_max = bpy.props.FloatProperty(name="Max", description = "Average cooling maximum", default = 500, max = 10000, min = 0, update=setcols)
    Scene.en_avecool_min = bpy.props.FloatProperty(name="Min", description = "Average cooling minimum", default = 0, max = 10000, min = 0, update=setcols)
    Scene.en_mincool_max = bpy.props.FloatProperty(name="Max", description = "Minimum cooling maximum", default = 3, max = 10, min = -9, update=setcols)
    Scene.en_mincool_min = bpy.props.FloatProperty(name="Min", description = "Minimum cooling minimum", default = -3, max = 9, min = -10, update=setcols)
    Scene.en_maxtemp_max = bpy.props.FloatProperty(name="Max", description = "Maximum temperature maximum", default = 25, max = 100, min = -100, update=setcols)
    Scene.en_maxtemp_min = bpy.props.FloatProperty(name="Min", description = "Maximum temperature minimum", default = 18, max = 50, min = -50, update=setcols)
    Scene.en_avetemp_max = bpy.props.FloatProperty(name="Max", description = "Average temperature maximum", default = 20, max = 40, min = 0, update=setcols)
    Scene.en_avetemp_min = bpy.props.FloatProperty(name="Min", description = "Average temperature minimum", default = 20, max = 30, min = 5, update=setcols)
    Scene.en_mintemp_max = bpy.props.FloatProperty(name="Max", description = "Minimum temperature maximum", default = 15, max = 30, min = 0, update=setcols)
    Scene.en_mintemp_min = bpy.props.FloatProperty(name="Min", description = "Minimum temperature minimum", default = 5, max = 30, min = 0, update=setcols)
    Scene.en_tothkwhm2_max = bpy.props.FloatProperty(name="Max", description = "Total heating per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_tothkwhm2_min = bpy.props.FloatProperty(name="Min", description = "Total heating per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_tothkwh_max = bpy.props.FloatProperty(name="Max", description = "Total heating maximum", default = 100, min = 1, update=setcols)
    Scene.en_tothkwh_min = bpy.props.FloatProperty(name="Min", description = "Total heating minimum", default = 5, min = 0, update=setcols)
    Scene.en_totckwhm2_max = bpy.props.FloatProperty(name="Max", description = "Total cooling per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_totckwhm2_min = bpy.props.FloatProperty(name="Min", description = "Total cooling per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_totckwh_max = bpy.props.FloatProperty(name="Max", description = "Total cooling maximum", default = 100, min = 1, update=setcols)
    Scene.en_totckwh_min = bpy.props.FloatProperty(name="Min", description = "Total cooling minimum", default = 5, min = 0, update=setcols)
    Scene.en_maxshg_max = bpy.props.FloatProperty(name="Max", description = "Maximum solar heat gain maximum", default = 1000, min = 1, update=setcols)
    Scene.en_maxshg_min = bpy.props.FloatProperty(name="Min", description = "Maximum solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_aveshg_max = bpy.props.FloatProperty(name="Max", description = "Average solar heat gain maximum", default = 500, min = 1, update=setcols)
    Scene.en_aveshg_min = bpy.props.FloatProperty(name="Min", description = "Average solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_minshg_max = bpy.props.FloatProperty(name="Max", description = "Minimum solar heat gain maximum", default = 100, min = 1, update=setcols)
    Scene.en_minshg_min = bpy.props.FloatProperty(name="Min", description = "Minimum solar heat gain minimum", default = 0, min = 0, update=setcols)
    Scene.en_totshgkwhm2_max = bpy.props.FloatProperty(name="Max", description = "Total solar heat gain per m2 floor area maximum", default = 100, min = 1, update=setcols)
    Scene.en_totshgkwhm2_min = bpy.props.FloatProperty(name="Min", description = "Total solar heat gain per m2 floor area minimum", default = 5, min = 0, update=setcols)
    Scene.en_totshgkwh_max = bpy.props.FloatProperty(name="Max", description = "Total solar heat gain maximum", default = 100, min = 1, update=setcols)
    Scene.en_totshgkwh_min = bpy.props.FloatProperty(name="Min", description = "Total solar heat gain minimum", default = 5, min = 0, update=setcols)
    Scene.bar_min = bpy.props.FloatProperty(name="Min", description = "Bar graph minimum", default = 0, update=setcols)
    Scene.bar_max = bpy.props.FloatProperty(name="Max", description = "Bar graph maximum", default = 100, update=setcols)
    Scene.vi_display_rp_fs = iprop("", "Point result font size", 4, 24, 24)
    Scene.vi_display_rp_fc = fvprop(4, "", "Font colour", [0.0, 0.0, 0.0, 1.0], 'COLOR', 0, 1)
    Scene.vi_display_rp_sh = bprop("", "Toggle for font shadow display",  False)
    Scene.vi_display_rp_fsh = fvprop(4, "", "Font shadow", [0.0, 0.0, 0.0, 1.0], 'COLOR', 0, 1)
    Scene.vi_display_rp_off = fprop("", "Surface offset for number display", 0, 5, 0.001)
    Scene.vi_disp_trans = bpy.props.FloatProperty(name="", description = "Sensing material transparency", min = 0, max = 1, default = 1, update = tupdate)
    Scene.vi_disp_wire = bpy.props.BoolProperty(name="", description = "Draw wire frame", default = 0, update=wupdate)
    Scene.li_disp_sv = EnumProperty(items=[("0", "Daylight Factor", "Display Daylight factor"),("1", "Sky view", "Display the Sky View")], name="", description = "Compliance data type", default = "0", update = liviresupdate)
    Scene.li_disp_sda = EnumProperty(items=[("0", "sDA (%)", "Display spatial Daylight Autonomy"), ("1", "ASE (hrs)", "Display the Annual Solar Exposure")], name="", description = "Compliance data type", default = "0", update = liviresupdate)
    Scene.li_disp_wr = EnumProperty(items=[("0", "Wind Speed", "Wind speed (m/s)"),("1", "Wind Direction", "Wind direction (deg from North)")], name="", description = "Compliance data type", default = "0", update = liviresupdate)
 #   Scene.li_disp_lh = EnumProperty(items=[("0", "Mluxhours", "Display mega luxhours"), ("1", "Visible Irradiance", "Display visible irradiance"), ("1", "Full Irradiance", "Display full irradiance")], name="", description = "Exposure data type", default = "0", update = liviresupdate)
#    Scene.li_projname=sprop("", "Name of the building project", 1024, '')
#    Scene.li_assorg = sprop("", "Name of the assessing organisation", 1024, '')
#    Scene.li_assind = sprop("", "Name of the assessing individual", 1024, '')
#    Scene.li_jobno = sprop("", "Project job number", 1024, '')
    Scene.li_disp_basic = EnumProperty(items=[("0", "Illuminance", "Display Illuminance values"), ("1", "Visible Irradiance", "Display Irradiance values"), ("2", "Full Irradiance", "Display Irradiance values"), ("3", "DF", "Display Daylight factor values")], name="", description = "Basic metric selection", default = "0", update = liviresupdate)
    Scene.li_disp_da = EnumProperty(items=[("0", "DA", "Daylight Autonomy"), ("1", "sDA", "Spatial Daylight Autonomy"), ("2", "UDILow", "Spatial Daylight Autonomy"), ("3", "UDISup", "Spatial Daylight Autonomy"),
                                             ("4", "UDIAuto", "Spatial Daylight Autonomy"), ("5", "UDIHigh", "Spatial Daylight Autonomy"), ("6", "ASE", "Annual sunlight exposure"), ("7", "Max lux", "Maximum lux level"),
                                             ("8", "Ave Lux", "Average lux level"), ("9", "Min lux", "Minimum lux level")], name="", description = "Result selection", default = "0", update = liviresupdate)
    Scene.li_disp_exp = EnumProperty(items=[("0", "LuxHours", "Display LuhHours values"), ("1", "Full Irradiance", "Display full spectrum radiation exposure values"), ("2", "Visible Irradiance", "Display visible spectrum radiation exposure values"),
                                              ("3", "Full Irradiance Density", "Display full spectrum radiation exposure values"), ("4", "Visible Irradiance Density", "Display visible spectrum radiation exposure values")], name="", description = "Result selection", default = "0", update = liviresupdate)
    Scene.li_disp_irrad = EnumProperty(items=[("0", "kWh", "Display kWh values"), ("1", "kWh/m2", "Display kWh/m2 values")], name="", description = "Result selection", default = "0", update = liviresupdate)
    (Scene.resaa_disp, Scene.resaws_disp, Scene.resawd_disp, Scene.resah_disp, Scene.resas_disp, Scene.reszt_disp, Scene.reszh_disp, Scene.reszhw_disp, Scene.reszcw_disp, Scene.reszsg_disp, Scene.reszppd_disp,
     Scene.reszpmv_disp, Scene.resvls_disp, Scene.resvmh_disp, Scene.resim_disp, Scene.resiach_disp, Scene.reszco_disp, Scene.resihl_disp, Scene.reszlf_disp, Scene.reszof_disp, Scene.resmrt_disp,
     Scene.resocc_disp, Scene.resh_disp, Scene.resfhb_disp, Scene.reszahw_disp, Scene.reszacw_disp, Scene.reshrhw_disp, Scene.restcvf_disp, Scene.restcmf_disp, Scene.restcot_disp, Scene.restchl_disp,
     Scene.restchg_disp, Scene.restcv_disp, Scene.restcm_disp, Scene.resldp_disp)  = resnameunits()

    (Scene.resazmaxt_disp, Scene.resazmint_disp, Scene.resazavet_disp,
     Scene.resazmaxhw_disp, Scene.resazminhw_disp, Scene.resazavehw_disp,
     Scene.resazth_disp, Scene.resazthm_disp,
     Scene.resazmaxcw_disp, Scene.resazmincw_disp, Scene.resazavecw_disp,
     Scene.resaztc_disp, Scene.resaztcm_disp,
     Scene.resazmaxco_disp, Scene.resazaveco_disp, Scene.resazminco_disp,
     Scene.resazlmaxf_disp, Scene.resazlminf_disp, Scene.resazlavef_disp,
     Scene.resazmaxshg_disp, Scene.resazminshg_disp, Scene.resazaveshg_disp,
     Scene.resaztshg_disp, Scene.resaztshgm_disp)  = aresnameunits()
    Scene.envi_flink = bprop("", "Associate flow results with the nearest object", False)

    nodeitems_utils.register_node_categories("Vi Nodes", vinode_categories)
    nodeitems_utils.register_node_categories("EnVi Nodes", envinode_categories)

    if update_chart_node not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_chart_node)

    if display_off not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(display_off)

    if mesh_index not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(mesh_index)

    if update_dir not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(update_dir)

def unregister():
    bpy.utils.unregister_module(__name__)
    nodeitems_utils.unregister_node_categories("Vi Nodes")
    nodeitems_utils.unregister_node_categories("EnVi Nodes")

    if update_chart_node in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_chart_node)

    if display_off in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(display_off)

    if mesh_index in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(mesh_index)

    if update_dir in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(update_dir)
