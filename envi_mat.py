# -*- coding:utf-8 -*-

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
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110- 1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import bpy
import os
import subprocess
import datetime
import shutil
import bmesh

from collections import OrderedDict
from bpy.props import (
    StringProperty, EnumProperty,
    IntProperty, CollectionProperty,
    FloatProperty
    )
from bpy.types import (
    Operator, PropertyGroup,
    Material, Object,
    Panel, Menu
    )
from bl_operators.presets import AddPresetBase
from .envi_func import epentry, epschedwrite
from .vi_func import (
    bprop, eprop, sprop,
    selobj, facearea, boundpoly, selmesh
    )

dtdf = datetime.date.fromordinal

caidict = {"0": "",
    "1": "Simple",
    "2": "TARP",
    "3": "CeilingDiffuser",
    "4": "AdaptiveConvectionAlgorithm"}

caodict = {"0": "",
    "1": "SimpleCombined",
    "2": "TARP",
    "3": "DOE-2",
    "4": "MoWiTT",
    "5": "AdaptiveConvectionAlgorithm"}


# Materials constants
METAL = {
    'Copper': ('Smooth', 200, 8900.0, 418.00, 0.72, 0.65, 0.65, 5),
    'Steel': ('Smooth', 50, 7800.0, 502.0, 0.12, 0.2, 0.2, 5),
    'Aluminium': ('Smooth', 210, 2700, 880.00, 0.22, 0.2, 0.2, 5),
    'Lead': ('Smooth', 35.3, 11340, 128.00, 0.05, 0.05, 0.05, 5)}

BRICK = {
    'Standard Brick': ('Rough', 0.8, 1800, 900.00, 0.900000, 0.600000, 0.600000, 100),
    'Inner brick': ('Rough', 0.62, 1800, 840.00, 0.93, 0.700000, 0.700000, 100),
    'Outer brick': ('Rough', 0.96, 2000, 650.00, 0.90, 0.930000, 0.930000, 100),
    'Vermiculite insulating brick': ('Rough', 0.27, 700, 840.00, 0.90, 0.650000, 0.650000, 100),
    'Honeycomb brick': ('Rough', 0.27, 1700, 1000.00, 0.90, 0.7, 0.7, 102),
    'Hollow terracota': ('Rough', 0.6, 845, 800, 0.90, 0.7, 0.7, 102)}

CLADDING = {
    'Stucco': ('Smooth', 0.692, 1858, 836.00, 0.900000, 0.9200000, 0.920000, 25),
    'Plaster board': ('Smooth', 0.7264, 1602, 836.00, 0.400000, 0.400000, 0.40000, 20),
    'Plaster': ('Smooth', 1.5, 1900, 840.00, 0.300000, 0.300000, 0.3000, 5),
    'Roof tiles': ('Smooth', 0.84, 1900, 840.00, 0.800000, 0.800000, 0.80000, 20)}

CONCRETE = {
    'Light mix concrete': ('MediumRough', 0.38, 1200.0, 653, 0.9, 0.65, 0.65, 100),
    'Aerated concrete block': ('Rough', 0.24, 750.0, 1000, 0.9, 0.65, 0.65, 100),
    'Inner concrete block': ('Rough', 0.51, 1400.0, 1000, 0.9, 0.65, 0.65, 100),
    'Heavy mix concrete': ('Rough', 1.4, 2100.0, 840.0, 0.90, 0.65, 0.65, 100),
    'Concrete Floor slab': ('MediumRough', 1.73, 2242.6, 836.0, 0.90, 0.65, 0.65, 100),
    'Hemcrete': ('Rough', 0.09, 330.0, 2100, 0.900000, 0.600000, 0.600000, 50),
    'Screed': ('MediumRough', 0.41, 1200.0, 2100, 0.900000, 0.600000, 0.600000, 50)}

WOOD = {
    'Wood flooring': ('MediumSmooth', 0.14, 600.0, 1210.0, 0.91, 0.65, 0.65, 25),
    'Parquet flooring': ('MediumSmooth', 0.17, 740.0, 2000.0, 0.90, 0.65, 0.65, 12),
    'Medium hardboard': ('MediumSmooth', 0.17, 740.0, 2000.0, 0.90, 0.65, 0.65, 12),
    'Plywood': ('MediumSmooth', 0.15, 700.0, 1420.0, 0.90, 0.65, 0.65, 25),
    'Chipboard': ('MediumSmooth', 0.15, 800.0, 2093.0, 0.91, 0.65, 0.65, 25),
    'OSB': ('MediumSmooth', 0.13, 640.0, 800.0, 0.91, 0.65, 0.65, 15),
    'Hardwood': ('MediumSmooth', 0.16, 720.8, 1255.2, 0.90, 0.78, 0.78, 50)}

STONE = {
    'Sandstone': ('MediumSmooth', 1.83, 2200.0, 712.0, 0.90, 0.6, 0.6, 200),
    'Limestone': ('MediumSmooth', 1.3, 2180.0, 720.0, 0.90, 0.6, 0.6, 200),
    'Clay tile': ('MediumSmooth', 0.85, 1900.0, 837.0, 0.90, 0.6, 0.6, 6),
    'Common earth': ('Rough', 1.28, 1460.0, 879.0, 0.90, 0.85, 0.85, 200),
    'Gravel': ('Rough', 1.28, 1460.0, 879.0, 0.90, 0.85, 0.85, 200),
    'Tuff': ('MediumRough', 0.4, 1400.0, 800.0, 0.90, 0.65, 0.65, 200),
    'Rammed earth': ('Rough', 1.25, 1540.0, 1260.0, 0.90, 0.65, 0.65, 250),
    'Sand': ('Rough', 0.2, 1500.0, 700.0, 0.90, 0.65, 0.65, 250)}

GAS = {
    'Air 20-50mm': ('Gas', 'Air', 0.17),
    'Horizontal Air 20-50mm Heat Down': ('Gas', 'Air', 0.21),
    'Horizontal Air 20-50mm Heat Up': ('Gas', 'Air', 0.17)}

WGAS = {
    'Argon': ('Gas', 'Argon', '', 0.2, 0.016),
    'Krypton': ('Gas', 'Krypton', '', 0.22, 0.00943),
    'Xenon': ('Gas', 'Xenon', '', 0.25, 0.00565),
    'Air': ('Gas', 'Air', '', 0.17, 0.024)}

GLASS = {
    'Clear 6mm': ('Glazing', 'SpectralAverage', '0', 6, 0.775, 0.071, 0.071, 0.881, 0.08, 0.08, 0.0, 0.84, 0.84, 0.9),
    'Clear 3mm': ('Glazing', 'SpectralAverage', '0', 3, 0.837, 0.075, 0.075, 0.898, 0.081, 0.081, 0.0, 0.84, 0.84, 0.9),
    'Clear 6mm LoE': ('Glazing', 'SpectralAverage', '0', 6, 0.60, 0.017, 0.22, 0.84, 0.055, 0.078, 0.0, 0.84, 0.1, 0.9),
    'Clear 3mm LoE': ('Glazing', 'SpectralAverage', '0', 3, 0.63, 0.19, 0.22, 0.85, 0.056, 0.079, 0.0, 0.84, 0.1, 0.9)}

INSULATION = {
    'Glass fibre quilt': ('Rough', 0.04, 12.0, 840.0, 0.9, 0.65, 0.65, 100),
    'EPS': ('MediumSmooth', 0.035, 15, 1000.0, 0.90, 0.7, 0.7, 100),
    'Cavity wall insul': ('Rough', 0.037, 300.0, 1000.0, 0.90, 0.6, 0.6, 100),
    'Roofing felt': ('Rough', 0.19, 960.0, 837.0, 0.90, 0.9, 0.9, 6),
    'Wilton wool carpet': ('Rough', 0.06, 186.0, 1360.0, 0.90, 0.60, 0.60, 5),
    'Thermawall TW50': ('MediumSmooth', 0.022, 32.000, 1500, 0.900000, 0.600000, 0.600000, 200),
    'Stramit': ('Rough', 0.1, 380.0, 2100, 0.900000, 0.600000, 0.600000, 50),
    'Straw bale': ('Rough', 0.07, 110.0, 2000, 0.900000, 0.600000, 0.600000, 50),
    'Foamglass': ('MediumSmooth', 0.04, 120.0, 840, 0.900000, 0.600000, 0.600000, 50),
    'Calsitherm': ('Rough', 0.059, 220.0, 1500, 0.900000, 0.600000, 0.600000, 50),
    'Cellulose (attic)': ('Rough', 0.04, 25.0, 1600, 0.900000, 0.600000, 0.600000, 200),
    'Thermafloor TF70': ('Smooth', 0.022, 32.0, 1500, 0.100000, 0.100000, 0.100000, 250),
    'Aerogel insulation': ('Smooth', 0.015, 2.0, 840, 0.100000, 0.100000, 0.100000, 60)}

PCM = {
    'PCM plaster board':
        ('Smooth', 0.7264, 1602, 836.00, 0.90, 0.92, 0.92, 20, 0.0, '-20.0:0.1 22:18260 22.1:32000 60:71000'),
    'DuPont Energain':
        ('Smooth', 0.16, 850, 2500, 0.90, 0.92, 0.92, 5, 0.0, '-9.0:0.001 15.0:93760 26.0:191185 80.0:332460')}


class envi_materials(object):
    '''Defines materials with a comma separated dictionary, with material name as key, giving
    (Roughness, Conductivity {W/m-K}, Density {kg/m3}, Specific Heat {J/kg-K}, Thermal Absorbtance,
    Solar Absorbtance, Visible Absorbtance, Default thickness)'''

    def __init__(self):

        self.metal_dat = OrderedDict(sorted(METAL.items()))
        self.brick_dat = OrderedDict(sorted(BRICK.items()))
        self.cladding_dat = OrderedDict(sorted(CLADDING.items()))
        self.concrete_dat = OrderedDict(sorted(CONCRETE.items()))
        self.wood_dat = OrderedDict(sorted(WOOD.items()))
        self.stone_dat = OrderedDict(sorted(STONE.items()))
        self.gas_dat = OrderedDict(sorted(GAS.items()))
        self.wgas_dat = OrderedDict(sorted(WGAS.items()))
        self.glass_dat = OrderedDict(sorted(GLASS.items()))
        self.insulation_dat = OrderedDict(sorted(INSULATION.items()))
        self.pcm_dat = OrderedDict(sorted(PCM.items()))

        self.namedict = OrderedDict()
        self.thickdict = OrderedDict()
        self.i = 0
        self.matdat = OrderedDict()
        for dat in (self.brick_dat, self.cladding_dat, self.concrete_dat, self.gas_dat, self.insulation_dat,
                    self.metal_dat, self.stone_dat, self.wood_dat, self.pcm_dat, self.glass_dat, self.wgas_dat):
            self.matdat.update(dat)

    def omat_write(self, idf_file, name, stringmat, thickness):
        params = ('Name', 'Roughness', 'Thickness (m)', 'Conductivity (W/m-K)', 'Density (kg/m3)',
                  'Specific Heat Capacity (J/kg-K)', 'Thermal Absorptance', 'Solar Absorptance', 'Visible Absorptance')
        paramvs = [name, stringmat[0], thickness] + stringmat[1:8]
        idf_file.write(epentry("Material", params, paramvs))

    def amat_write(self, idf_file, name, stringmat):
        params = ('Name', 'Resistance')
        paramvs = (name, stringmat[0])
        idf_file.write(epentry("Material:AirGap", params, paramvs))

    def tmat_write(self, idf_file, name, stringmat, thickness):
        params = ('Name', 'Optical Data Type', 'Window Glass Spectral Data Set Name', 'Thickness (m)',
          'Solar Transmittance at Normal Incidence', 'Front Side Solar Reflectance at Normal Incidence',
          'Back Side Solar Reflectance at Normal Incidence', 'Visible Transmittance at Normal Incidence',
          'Front Side Visible Reflectance at Normal Incidence', 'Back Side Visible Reflectance at Normal Incidence',
          'Infrared Transmittance at Normal Incidence', 'Front Side Infrared Hemispherical Emissivity',
          'Back Side Infrared Hemispherical Emissivity', 'Conductivity (W/m-K)',
          'Dirt Correction Factor for Solar and Visible Transmittance', 'Solar Diffusing')

        paramvs = [name] + stringmat[1:3] + [thickness]
        paramvs += ['{:.3f}'.format(float(sm)) for sm in stringmat[4:-1]]
        paramvs += [1, ('No', 'Yes')[stringmat[-1]]]

        idf_file.write(epentry("WindowMaterial:{}".format(stringmat[0]), params, paramvs))

    def gmat_write(self, idf_file, name, stringmat, thickness):
        params = ('Name', 'Gas Type', 'Thickness')
        paramvs = [name] + [stringmat[1]] + [thickness]
        idf_file.write(epentry("WindowMaterial:Gas", params, paramvs))

    def pcmmat_write(self, idf_file, name, stringmat):
        params = ('Name', 'Temperature Coefficient for Thermal Conductivity (W/m-K2)')
        paramvs = (name, stringmat[0])
        for i, te in enumerate(stringmat[1].split()):
            params += ('Temperature {} (C)'.format(i), 'Enthalpy {} (J/kg)'.format(i))
            paramvs += (te.split(':')[0], te.split(':')[1])
        idf_file.write(epentry("MaterialProperty:PhaseChange", params, paramvs))


# @NOTE: use blender internal preset system instead of this
"""
    WALL = {'External Wall 1': ('Standard Brick', 'Thermawall TW50', 'Inner concrete block'),
        'Kingston PH 1': ('Plywood', 'EPS', 'Plywood'),
        'Party Wall 1': ('Plaster board', 'Standard Brick', 'Plaster board'),
        'SIP': ('OSB', 'EPS', 'OSB')}

    CEIL = {'Ceiling 1': ('Chipboard', 'EPS', 'Plaster board')}

    FLOOR = {
        'Ground Floor 1': ('Common earth',
             'Gravel',
             'Heavy mix concrete',
             'Horizontal Air 20-50mm Heat Down',
             'Chipboard'),
        'Kingston PH 1': ('Common earth', 'Gravel', 'EPS', 'Heavy mix concrete')}

    ROOF = {'Roof 1': ('Clay tile', 'Roofing felt', 'Plywood')}

    GLAZE = {'Standard Double Glazing': ('Clear 3mm', 'Air', 'Clear 3mm'),
        'Low-E Double Glazing': ('Clear 3mm LoE', 'Air', 'Clear 3mm'),
        'PassivHaus': ('Clear 3mm LoE', 'Argon', 'Clear 3mm LoE', 'Argon', 'Clear 3mm')}

    DOOR = {'Internal Door 1': ('Chipboard', 'Hardwood', 'Chipboard')}

    FLOOR.update(CEIL)
"""


class envi_constructions(object):
    """
    def __init__(self):

        self.wall_con = OrderedDict(sorted(WALL.items()))
        self.ceil_con = OrderedDict(sorted(CEIL.items()))
        self.floor_con = OrderedDict(sorted(FLOOR.items()))
        self.roof_con = OrderedDict(sorted(ROOF.items()))
        self.door_con = OrderedDict(sorted(DOOR.items()))
        self.glaze_con = OrderedDict(sorted(GLAZE.items()))
        self.p = 0

        self.propdict = {'Wall': self.wall_con,
                        'Floor': self.floor_con,
                        'Roof': self.roof_con,
                        'Ceiling': self.floor_con,
                        'Door': self.door_con,
                        'Window': self.glaze_con}
    """
    def con_write(self, idf_file, contype, name, nl, mn, cln):
        params = ['Name', 'Outside layer'] + ['Layer {}'.format(i + 1) for i in range(len(cln) - 1)]
        paramvs = [mn] + cln
        # '{}-{}'.format(con[name][0], nl)]
        idf_file.write(epentry('Construction', params, paramvs))


def enum_material_group(self, context):

    if self.con_type in ('Wall', 'Roof', 'Floor', 'Door', 'Ceiling'):

        typelist = [("0", "Brick", "Choose a material from the brick database"),
                    ("1", "Cladding", "Choose a material from the cladding database"),
                    ("2", "Concrete", "Choose a material from the concrete database"),
                    ("3", "Metal", "Choose a material from the metal database"),
                    ("4", "Stone", "Choose a material from the stone database"),
                    ("5", "Wood", "Choose a material from the wood database"),
                    ("6", "Gas", "Choose a material from the gas database"),
                    ("7", "Insulation", "Choose a material from the insulation database"),
                    ("8", "PCM", "Choose a material from the phase change database")]

    elif self.con_type == 'Window':
        if not self.envi_index % 2:
            typelist = [("9", "Glass", "Choose a material from the glass database")]
        else:
            typelist = [("10", "Gas", "Choose a material from the gas database")]
    else:
        typelist = [('', '', '')]
    return typelist


def enum_material_name(self, context):
    em = envi_materials()

    if self.con_type in ('Wall', 'Roof', 'Floor', 'Door', 'Ceiling'):

        matdict = {'0': em.brick_dat.keys(),
                    '1': em.cladding_dat.keys(),
                    '2': em.concrete_dat.keys(),
                    '3': em.metal_dat.keys(),
                    '4': em.stone_dat.keys(),
                    '5': em.wood_dat.keys(),
                    '6': em.gas_dat.keys(),
                    '7': em.insulation_dat.keys(),
                    '8': em.pcm_dat.keys()
                    }
    elif self.con_type == 'Window':
        if not self.envi_index % 2:
            matdict = {'9': em.glass_dat.keys()}
        else:
            matdict = {'10': em.wgas_dat.keys()}
    else:
        return [('', '', '')]

    return [((mat, mat, 'Layer material')) for mat in list(matdict[self.envi_material_group])]


def enum_wgas_name(self, context):
    em = envi_materials().wgas_dat.keys()
    return [((mat, mat, 'Gas type')) for mat in list(em)]


def envi_con_list(self, context):
    ec = envi_constructions()
    idx = ("Wall", "Roof", "Floor", "Ceiling", "Door", "Window").index(self.con_type)
    mats = (ec.wall_con, ec.roof_con, ec.floor_con, ec.ceil_con, ec.door_con, ec.glaze_con)[idx]
    return [(mat, mat, 'Construction') for mat in mats]


def retuval(self, context):

    resists, em = [], envi_materials()

    for l, lay in enumerate(self.layers):

        # database
        if lay.envi_layer == '1':
            if em.matdat[lay.envi_material_name][0] == 'Gas':
                dtc = em.matdat[lay.envi_material_name][2]
            else:
                dtc = em.matdat[lay.envi_material_name][1]
            resists.append(
                (0.001 * lay.export_thi / float(dtc), float(dtc))[em.matdat[lay.envi_material_name][0] == 'Gas']
                )

        # user def
        if lay.envi_layer == '2':
            resists.append(0.001 * lay.export_thi / lay.export_tc)

    res = sum(resists)
    if res != 0:
        uv = 1 / (res + 0.12 + 0.08)
    else:
        uv = 0
    # self.material_uv = '{:.3f}'.format(uv)
    return uv


def update_material_name(self, context):
    """
        Set default thickness and material name
    """
    print("update_material_name: %s" % (self.envi_material_name))
    if self.envi_layer != '0':
        em = envi_materials()
        mdat = em.matdat[self.envi_material_name]
        self.export_name = self.envi_material_name
        if self.con_type in ('Wall', 'Roof', 'Floor', 'Door', 'Ceiling'):
            if self.envi_material_group in {"0", "1", "2", "3", "4", "5", "7"}:
                # omat
                """
                    ('Name', 'Roughness', 'Thickness (m)', 'Conductivity (W/m-K)', 'Density (kg/m3)',
                      'Specific Heat Capacity (J/kg-K)', 'Thermal Absorptance', 'Solar Absorptance',
                      'Visible Absorptance')
                """
                for i, prop in enumerate(["rough", "tc", "rho", "shc", "tab", "sab", "vab", "thi"]):
                    setattr(self, "export_" + prop, mdat[i])
            elif self.envi_material_group in {"6"}:
                # amat 20 to 50 mm
                # 'Name', 'Resistance'
                self.export_wgas = mdat[1]
                self.export_res = mdat[2]
                self.export_thi = 20
            elif self.envi_material_group in {"8"}:
                # PCM
                for i, prop in enumerate(["rough", "tc", "rho", "shc", "tab",
                                            "sab", "vab", "thi", "tctc", "tempsemps"]):
                    setattr(self, "export_" + prop, mdat[i])

        elif self.con_type == 'Window':
            if not self.envi_index % 2:
                # tmat (are in m)
                """
                ('Name', 'Optical Data Type', 'Window Glass Spectral Data Set Name', 'Thickness (m)',
                'Solar Transmittance at Normal Incidence', 'Front Side Solar Reflectance at Normal Incidence',
                 'Back Side Solar Reflectance at Normal Incidence', 'Visible Transmittance at Normal Incidence',
                 'Front Side Visible Reflectance at Normal Incidence',
                 'Back Side Visible Reflectance at Normal Incidence',
                 'Infrared Transmittance at Normal Incidence', 'Front Side Infrared Hemispherical Emissivity',
                 'Back Side Infrared Hemispherical Emissivity', 'Conductivity (W/m-K)',
                 'Dirt Correction Factor for Solar and Visible Transmittance', 'Solar Diffusing')
                """
                # , "dcf", "sdiff"
                for i, prop in enumerate(["name", "odt", "sds", "thi", "stn", "fsn",
                            "bsn", "vtn", "fvrn", "bvrn", "itn", "fie", "bie", "tc"]):
                    setattr(self, "export_" + prop, mdat[i])
            else:
                # gmat (window) default 14mm
                self.export_wgas = self.envi_material_name
                self.export_thi = 14


def update_con_type(self, context):
    """
        Update enumarator for presets
    """
    if self.con_type != 'None':
        enum = enum_material_group(self, context)
        print("enum_material_group: %s" % (enum))
        self.rna_type.envi_material_group = enum
        self.envi_material_group = enum[0][0]
        print("update_con_type: %s" % (self.con_type))


def update_material_group(self, context):
    """
        Update enumarator for presets
    """
    if self.con_type != 'None' and self.envi_layer != '0':
        enum = enum_material_name(self, context)
        print("enum_material_name: %s" % (enum))
        self.rna_type.envi_material_name = enum
        print("update_material_group")
        self.envi_material_name = enum[0][0]


class VISUITE_Material_EnviLayer(PropertyGroup):
    """
        EnVi layer properties
        NOTE:
            load order from preset is important
            alphanum sorted properties
            envi_material_group and _name
            must stay before any export param
            to update enumerators while loading presets
            export must stay after
    """
    con_type = StringProperty(update=update_con_type)
    envi_index = IntProperty(description="Layer index")
    envi_layer = EnumProperty(
        items=(("0", "None", "Not present"),
            ("1", "Database", "Select from databse"),
            ("2", "Custom", "Define custom material properties")),
        name="",
        description="Composition of the layer",
        default="0",
        update=update_material_group)

    envi_material_group = EnumProperty(
        items=enum_material_group,
        name="Material group",
        description="Material group type",
        update=update_material_group)

    envi_material_name = EnumProperty(
        items=enum_material_name,
        name="Material name",
        update=update_material_name)

    export_name = sprop("Name:", "Layer name", 0, "")

    export_tc = FloatProperty(
        name="Conductivity",
        description="Thermal Conductivity",
        min=0,
        default=0.5,
        precision=4)
    export_rough = eprop([("VeryRough", "VeryRough", "Roughness"),
            ("Rough", "Rough", "Roughness"),
            ("MediumRough", "MediumRough", "Roughness"),
            ("MediumSmooth", "MediumSmooth", "Roughness"),
            ("Smooth", "Smooth", "Roughness"),
            ("VerySmooth", "VerySmooth", "Roughness")],
            "Material surface roughness", "specify the material rughness for convection calculations", "Rough")
    export_rho = FloatProperty(
        name="Density",
        description="Density (kg/m3)",
        min=0,
        default=1000,
        precision=4)
    export_shc = FloatProperty(
        name="SHC",
        description="Specific Heat Capacity (J/kgK)",
        min=0,
        default=1000,
        precision=4)
    export_thi = FloatProperty(
        name="Thickness",
        description="Thickness (mm)",
        min=0,
        default=100)
    export_tab = FloatProperty(
        name="TA",
        description="Thermal Absorptance",
        min=0.001,
        max=1,
        default=0.8,
        precision=4)
    export_sab = FloatProperty(
        name="SA",
        description="Solar Absorptance",
        min=0.001,
        max=1,
        default=0.6,
        precision=4)
    export_vab = FloatProperty(
        name="VA",
        description="Visible Absorptance",
        min=0.001,
        default=0.6,
        precision=4)
    export_odt = eprop([("SpectralAverage", "SpectralAverage", "Optical Data Type")],
                        "", "Optical Data Type", "SpectralAverage")
    export_sds = eprop([("0", "", "Window Glass Spectral Data Set Name")],
                        "Construction Make-up:", "Window Glass Spectral Data Set Name", "0")
    export_stn = FloatProperty(
        name="STN",
        description="Solar Transmittance at Normal Incidence",
        min=0,
        max=1,
        default=0.9,
        precision=4)
    export_fsn = FloatProperty(
        name="FSN",
        description="Front Side Solar Reflectance at Normal Incidence",
        min=0,
        max=1,
        default=0.075,
        precision=4)
    export_bsn = FloatProperty(
        name="BSN",
        description="Back Side Solar Reflectance at Normal Incidence",
        min=0,
        max=1,
        default=0.075,
        precision=4)
    export_vtn = FloatProperty(
        name="VTN",
        description="Visible Transmittance at Normal Incidence",
        min=0,
        max=1,
        default=0.9,
        precision=4)
    export_fvrn = FloatProperty(
        name="FVRN",
        description="Front Side Visible Reflectance at Normal Incidence",
        min=0,
        max=1,
        default=0.08,
        precision=4)
    export_bvrn = FloatProperty(
        name="BVRN",
        description="Back Side Visible Reflectance at Normal Incidence",
        min=0,
        max=1,
        default=0.08,
        precision=4)
    export_itn = FloatProperty(
        name="ITN",
        description="Infrared Transmittance at Normal Incidence",
        min=0,
        max=1,
        default=0.0,
        precision=4)
    export_fie = FloatProperty(
        name="FIE",
        description="Front Side Infrared Hemispherical Emissivity",
        min=0,
        max=1,
        default=0.84,
        precision=4)
    export_bie = FloatProperty(
        name="BIE",
        description="Back Side Infrared Hemispherical Emissivity",
        min=0,
        max=1,
        default=0.84,
        precision=4)
    export_dcf = FloatProperty(
        name="DCF",
        description="Dirt Correction Factor for Solar and Visible Transmittance",
        min=0,
        max=1,
        default=0,
        precision=4)
    export_sdiff = bprop("Translucent:", "Solar Diffusing", 0)
    export_wgas = EnumProperty(name="Gas Type:", items=enum_wgas_name)
    export_tctc = FloatProperty(
        name="TCTC",
        description="Temperature coefficient for thermal conductivity",
        min=0,
        max=50,
        default=0.0,
        precision=4)
    export_tempsemps = sprop("Temps:Enthalpies:", "Temperatures/Enthalpy pairs", 1024, "")

    def draw(self, context, layout):
        if self.envi_index == 0:
            layout.prop(self, "envi_layer", text="Outside")
        else:
            layout.prop(self, "envi_layer", text="Layer " + str(self.envi_index + 1))

        if self.envi_layer != '0':
            layout.prop(self, "envi_material_group")

        if self.envi_layer == '1':
            layout.prop(self, "envi_material_name")
            layout.prop(self, "export_thi")

        elif self.envi_layer == '2':
            if self.envi_material_group == '8':
                layout.prop(self, "export_tctc")
                layout.prop(self, "export_tempsemps")
            else:
                if self.con_type != 'Window':
                    row = layout.row()
                    for end in ('name', 0, 'thi', 'tc', 0, 'rho', 'shc', 0, 'tab', 'sab', 0, 'vab', 'rough'):
                        if end:
                            row.prop(self, '{}{}'.format("export_", end))
                        else:
                            row = layout.row()

                else:
                    layout.prop(self, "export_name")
                    if self.envi_index % 2:
                        layout.prop(self, "export_wgas")
                        layout.prop(self, "export_thi", text="Gas thickness")
                    else:
                        row = layout.row()
                        for end in ('odt', 0, 'thi', 'tc', 0,
                                    'stn', 'fsn', 'bsn', 0,
                                    'vtn', 'fvrn', 'bvrn', 0,
                                    'itn', 'fie', 'bie', 0, 'sds', 'sdiff'):
                            if end:
                                row.prop(self, '{}{}'.format("export_", end))
                            else:
                                row = layout.row()


def update_layers(self, context):
    for i in range(len(self.layers), self.n_layers, -1):
        self.layers.remove(i - 1)
    # add layers
    for i in range(len(self.layers), self.n_layers):
        self.layers.add()
    for i, layer in enumerate(self.layers):
        layer.envi_index = i
        if layer.con_type != self.con_type:
            layer.con_type = self.con_type


class VISUITE_Material_Envi(PropertyGroup):
    """
        EnVi material properties
    """
    layers = CollectionProperty(
        type=VISUITE_Material_EnviLayer,
        description="Envi layers",
        name="Layers")
    n_layers = IntProperty(
        name="Layers",
        min=1,
        default=1,
        description="Layers count",
        update=update_layers)
    con_type = EnumProperty(
        items=[("Wall", "Wall", "Wall construction"),
            ("Floor", "Floor", "Ground floor construction"),
            ("Roof", "Roof", "Roof construction"),
            ("Ceiling", "Ceiling", "Ceiling construction"),
            ("Window", "Window", "Window construction"),
            ("Door", "Door", "Door construction"),
            ("Shading", "Shading", "Shading material"),
            ("None", "None", "Surface to be ignored")
        ],
        name="EnVi Construction Type:",
        description="Specify the construction type",
        default="None",
        update=update_layers)
    boundary = bprop("Intrazone Boundary", "Flag to siginify whether the material represents a zone boundary", False)
    afsurface = bprop("Airflow surface", "Flag to siginify whether the material represents an airflow surface", False)
    thermalmass = bprop("Thermal mass", "Flag to siginify whether the material represents thermal mass", False)
    # ?? not exposed / exported ??
    aperture = eprop([("0", "External", "External facade airflow component", 0),
                      ("1", "Internal", "Zone boundary airflow component", 1)],
                      "Aperture", "Position of the airflow component", "0")
    material_uv = StringProperty(default="N/A")
    """
    # @NOTE: using internal preset system instead
    con_makeup = eprop([
        ("0", "Pre-set", "Construction pre-set"),
        ("1", "Layers", "Custom layers"),
        ("2", "Dummy", "Adiabatic")], "",
        "Pre-set construction of custom layers", "0")
    """
    export = bprop("Material Export", "Flag to tell EnVi to export this material", False)
    shad_att = bprop("Attached", "Flag to specify shading attached to the building", False)

    def draw(self, context, layout):

        layout.prop(self, "con_type")
        uv = retuval(self, context)
        layout.label('U-value (W/m^2.K): {:.3f}'.format(uv))

        if self.con_type not in ("Aperture", "Shading", "None"):
            layout.prop(self, "boundary")
            layout.prop(self, "afsurface")

            if not self.boundary and not self.afsurface:
                layout.prop(self, "thermalmass")

            row = layout.row(align=True)
            row.prop(self, "n_layers")
            row.operator("visuite.envi_material_layer_add", text="", icon="ZOOMIN")
            row.operator("visuite.envi_material_layer_remove", text="", icon="ZOOMOUT")

            for layer in self.layers:
                box = layout.box()
                layer.draw(context, box)

    @classmethod
    def datablock(cls, mat):
        if mat and len(mat.visuite_envi) > 0:
            return mat.visuite_envi[0]
        return None


class VISUITE_Object_Envi(PropertyGroup):
    type = eprop([
        ("0", "Thermal", "Thermal Zone"),
        ("1", "Shading", "Shading Object"),
        ("2", "Chimney", "Thermal Chimney Object")],
        "EnVi object type", "Specify the EnVi object type", "0")
    oca = eprop([
        ("0", "Default", "Use the system wide convection algorithm"),
        ("1", "Simple", "Use the simple convection algorithm"),
        ("2", "TARP", "Use the detailed convection algorithm"),
        ("3", "DOE-2", "Use the Trombe wall convection algorithm"),
        ("4", "MoWitt", "Use the adaptive convection algorithm"),
        ("5", "Adaptive", "Use the adaptive convection algorithm")],
        "Outside convection", "Specify the EnVi zone outside convection algorithm", "0")
    ica = eprop([
        ("0", "Default", "Use the system wide convection algorithm"),
        ("1", "Simple", "Use the simple convection algorithm"),
        ("2", "TARP", "Use the detailed convection algorithm"),
        ("3", "CeilingDiffuser", "Use the forced convection algorithm"),
        ("4", "Adaptive", "Use the adaptive convection algorithm")],
        "Inside convection", "Specify the EnVi zone inside convection algorithm", "0")

    @classmethod
    def datablock(cls, o):
        if o and len(o.visuite_envi) > 0:
            return o.visuite_envi[0]
        return None

    def draw(self, context, layout):
        layout.prop(self, "type")
        if self.type == '0':
            layout.prop(self, "ica")
            layout.prop(self, "oca")


class VISUITE_OP_envi_material_layer_add(Operator):
    bl_idname = "visuite.envi_material_layer_add"
    bl_label = "Add a layer"
    bl_description = "Add a layer"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and \
            len(context.object.active_material.visuite_envi) > 0

    def execute(self, context):
        mat = context.object.active_material
        mat.visuite_envi[0].n_layers += 1
        return {'FINISHED'}


class VISUITE_OP_envi_material_layer_remove(Operator):
    bl_idname = "visuite.envi_material_layer_remove"
    bl_label = "Remove a layer"
    bl_description = "Remove a layer"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and \
            len(context.object.active_material.visuite_envi) > 0

    def execute(self, context):
        mat = context.object.active_material
        if mat.visuite_envi[0].n_layers > 1:
            mat.visuite_envi[0].n_layers -= 1
        return {'FINISHED'}


class VISUITE_OP_envi_material_add(Operator):
    bl_idname = "visuite.envi_material_add"
    bl_label = "Enable Energy+"
    bl_description = "Add Energy+ parameters"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material is not None

    def execute(self, context):
        mat = context.object.active_material
        if len(mat.visuite_envi) < 1:
            mat.visuite_envi.add()
            update_layers(mat.visuite_envi[0], context)
        return {'FINISHED'}


class VISUITE_OP_envi_material_remove(Operator):
    bl_idname = "visuite.envi_material_remove"
    bl_label = "Disable Energy+"
    bl_description = "Delete Energy+ parameters"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material is not None

    def execute(self, context):
        mat = context.object.active_material
        if len(mat.visuite_envi) > 0:
            mat.visuite_envi.remove(0)
        return {'FINISHED'}


class VISUITE_OP_envi_object_add(Operator):
    bl_idname = "visuite.envi_object_add"
    bl_label = "Enable Energy+"
    bl_description = "Add Energy+ parameters"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o and not VISUITE_Object_Envi.datablock(o)

    def execute(self, context):
        o = context.active_object
        o.visuite_envi.add()
        return {'FINISHED'}


class VISUITE_OP_envi_object_remove(Operator):
    bl_idname = "visuite.envi_object_remove"
    bl_label = "Disable Energy+"
    bl_description = "Delete Energy+ parameters"
    bl_category = 'VI Suite'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return VISUITE_Object_Envi.datablock(context.active_object)

    def execute(self, context):
        o = context.active_object
        o.visuite_envi.remove(0)
        return {'FINISHED'}


class VISUITE_OP_envi_preset(AddPresetBase, Operator):
    """Envi Preset"""
    bl_idname = "visuite.envi_preset"
    bl_label = "Envi Preset"
    preset_menu = 'VISUITE_MT_envi_preset'

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return o is not None and \
            o.active_material is not None

    @property
    def preset_subdir(self):
        return "visuite_envi"

    @property
    def blacklist(self):
        """
            properties black list for presets
            may override on addon basis
        """
        return []

    @property
    def preset_values(self):
        blacklist = self.blacklist
        blacklist.extend(bpy.types.Mesh.bl_rna.properties.keys())
        d = getattr(bpy.context.active_object.active_material, self.preset_subdir)[0]
        props = d.rna_type.bl_rna.properties.items()
        ret = []
        for prop_id, prop in props:
            if prop_id not in blacklist:
                if not (prop.is_hidden or prop.is_skip_save):
                    ret.append("d.%s" % prop_id)
        ret.sort()
        return ret

    def execute(self, context):
        import os

        if hasattr(self, "pre_cb"):
            self.pre_cb(context)

        preset_menu_class = getattr(bpy.types, self.preset_menu)

        is_xml = getattr(preset_menu_class, "preset_type", None) == 'XML'

        if is_xml:
            ext = ".xml"
        else:
            ext = ".py"

        if not self.remove_active:
            name = self.name.strip()
            if not name:
                return {'FINISHED'}

            filename = self.as_filename(name)

            target_path = os.path.join("presets", self.preset_subdir)
            target_path = bpy.utils.user_resource('SCRIPTS',
                                                  target_path,
                                                  create=True)

            if not target_path:
                self.report({'WARNING'}, "Failed to create presets path")
                return {'CANCELLED'}

            filepath = os.path.join(target_path, filename) + ext

            if hasattr(self, "add"):
                self.add(context, filepath)
            else:
                print("Writing Preset: %r" % filepath)

                if is_xml:
                    import rna_xml
                    rna_xml.xml_file_write(context,
                                           filepath,
                                           preset_menu_class.preset_xml_map)
                else:

                    def rna_recursive_attr_expand(value, rna_path_step, level):
                        if isinstance(value, bpy.types.PropertyGroup):
                            keys = value.bl_rna.properties.keys()
                            keys.sort()
                            for sub_value_attr in keys:
                                if sub_value_attr == "rna_type":
                                    continue
                                sub_value = getattr(value, sub_value_attr)
                                rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
                        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
                            file_preset.write("%s.clear()\n" % rna_path_step)
                            for sub_value in value:
                                file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
                                rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
                        else:
                            # convert thin wrapped sequences
                            # to simple lists to repr()
                            try:
                                value = value[:]
                            except:
                                pass

                            file_preset.write("%s = %r\n" % (rna_path_step, value))

                    file_preset = open(filepath, 'w')
                    file_preset.write("import bpy\n")

                    if hasattr(self, "preset_defines"):
                        for rna_path in self.preset_defines:
                            exec(rna_path)
                            file_preset.write("%s\n" % rna_path)
                        file_preset.write("\n")

                    for rna_path in self.preset_values:
                        value = eval(rna_path)
                        rna_recursive_attr_expand(value, rna_path, 1)

                    file_preset.close()

            preset_menu_class.bl_label = bpy.path.display_name(filename)

        else:
            preset_active = preset_menu_class.bl_label

            # fairly sloppy but convenient.
            filepath = bpy.utils.preset_find(preset_active,
                                             self.preset_subdir,
                                             ext=ext)

            if not filepath:
                filepath = bpy.utils.preset_find(preset_active,
                                                 self.preset_subdir,
                                                 display_name=True,
                                                 ext=ext)

            if not filepath:
                return {'CANCELLED'}

            try:
                if hasattr(self, "remove"):
                    self.remove(context, filepath)
                else:
                    os.remove(filepath)
            except Exception as e:
                self.report({'ERROR'}, "Unable to remove preset: %r" % e)
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            # XXX, stupid!
            preset_menu_class.bl_label = "Presets"

        if hasattr(self, "post_cb"):
            self.post_cb(context)

        return {'FINISHED'}

    @property
    def preset_defines(self):
        return [
            "d = bpy.context.active_object.active_material.visuite_envi[0]"
        ]


class VISUITE_MT_envi_preset(Menu):
    bl_label = "Envi Presets"
    preset_subdir = "visuite_envi"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class VISUITE_PT_envi_material(Panel):
    bl_label = "VI-Suite Envi Material"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        o = context.active_object
        return VISUITE_Object_Envi.datablock(o)

    def draw(self, context):
        layout = self.layout
        o = context.active_object
        d = VISUITE_Material_Envi.datablock(o.active_material)

        if d is None:
            layout.operator("visuite.envi_material_add")
        else:
            layout.operator("visuite.envi_material_remove")
            row = layout.row(align=True)
            row.menu("VISUITE_MT_envi_preset", bpy.types.VISUITE_MT_envi_preset.bl_label)
            row.operator("visuite.envi_preset", text="", icon='ZOOMIN')
            row.operator("visuite.envi_preset", text="", icon='ZOOMOUT').remove_active = True
            d.draw(context, layout)


class VISUITE_PT_envi_object(Panel):
    bl_label = "VI-Suite Envi Object"
    bl_space_type = "PROPERTIES"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.active_object

    def draw(self, context):
        layout = self.layout
        o = context.active_object
        d = VISUITE_Object_Envi.datablock(o)

        if d is None:
            layout.operator("visuite.envi_object_add")
        else:
            layout.operator("visuite.envi_object_remove")
            if o.type == 'MESH':
                box = layout.box()
                d.draw(context, box)


def pregeo(context, op):
    scene = context.scene
    bpy.data.scenes[0].layers[0:2] = True, False
    if context.active_object and context.active_object.mode == 'EDIT':
        bpy.ops.object.editmode_toggle()
    for o in [o for o in scene.objects if o.layers[1]]:
        scene.objects.unlink(o)
        bpy.data.objects.remove(o)
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in bpy.data.materials:
        d = VISUITE_Material_Envi.datablock(mat)
        if d:
            d.export = False
        if mat.users == 0:
            bpy.data.materials.remove(mat)

    # vi_type 1 => Envi Zone
    enviobjs = [o for o in scene.objects if VISUITE_Object_Envi.datablock(o) and o.layers[0] and o.hide is False]

    if not [ng for ng in bpy.data.node_groups if ng.bl_label == 'EnVi Network']:
        bpy.ops.node.new_node_tree(type='EnViN', name="EnVi Network")
        for screen in bpy.data.screens:
            for area in [
                    area for area in screen.areas
                    if area.type == 'NODE_EDITOR' and area.spaces[0].tree_type == 'ViN'
                    ]:
                area.spaces[0].node_tree = bpy.data.node_groups[op.nodeid.split('@')[1]]

    enng = [ng for ng in bpy.data.node_groups if ng.bl_label == 'EnVi Network'][0]
    enng.use_fake_user = True
    enng['enviparams'] = {'wpca': 0, 'wpcn': 0, 'crref': 0, 'afn': 0, 'pcm': 0}

    for node in enng.nodes:
        if hasattr(node, 'zone'):
            # z_name without en_ prefix
            z_name = node.zone[3:]
            # d.type: 0: Thermal 1:Shading 2:Chimney
            d = VISUITE_Object_Envi.datablock(scene.objects[z_name])
            if ((z_name not in [o.name for o in enviobjs]) or
                    (d and node.bl_idname == 'EnViZone' and d.type != '0') or
                    (d and node.bl_idname == 'EnViTC' and d.type != '2')):
                enng.nodes.remove(node)

    for o in enviobjs:

        """
        for k in o.keys():
            if k not in ('visuite_envi', 'vi_type', 'oca', 'ica'):
                del o[k]
        """
        d = VISUITE_Object_Envi.datablock(o)
        omats = [(m, VISUITE_Material_Envi.datablock(m)) for m in o.data.materials]

        if d.type in ('0', '2') and not omats:
            op.report({'ERROR'}, 'Object {} is specified as a thermal zone but has no materials'.format(o.name))
        elif None in omats:
            op.report({'ERROR'}, 'Object {} has an empty material slot'.format(o.name))

        # Thermal / Chimney / envi_type
        elif d.type in ('0', '2'):
            ezdict = {'0': 'EnViZone', '2': 'EnViTC'}

            dcdict = {'Wall': (1, 1, 1),
                'Partition': (1, 1, 0.0),
                'Window': (0, 1, 1),
                'Roof': (0, 1, 0),
                'Ceiling': (1, 1, 0),
                'Floor': (0.44, 0.185, 0.07),
                'Shading': (1, 0, 0)}

            ofa = sum([facearea(o, face) for face in o.data.polygons
                        if omats[face.material_index][1] and omats[face.material_index][1].con_type == 'Floor'])

            o["floorarea"] = ofa if ofa else 0.001

            for m, md in omats:
                if md:
                    em_mat = bpy.data.materials.get('en_' + m.name)
                    if not em_mat:
                        em_mat = m.copy()
                        em_mat.name = 'en_' + m.name
                    for layer in md.layers:
                        if '8' in (layer.envi_material_group):
                            enng['enviparams']['pcm'] = 1

            selobj(scene, o)

            bpy.ops.object.duplicate()
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            en_o = scene.objects.active
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')
            selmesh('desel')
            enomats = [enom for enom in en_o.data.materials if enom]

            o.select, en_o.select, en_o.name = False, True, 'en_' + o.name

            en_o.layers[1], en_o.layers[0], bpy.data.scenes[0].layers[0:2] = True, False, (False, True)

            mis = [f.material_index for f in en_o.data.polygons]

            for s, sm in enumerate(en_o.material_slots):
                md = VISUITE_Material_Envi.datablock(sm.material)
                if md:
                    mct = 'Partition' if md.con_type == 'Wall' and md.boundary else md.con_type
                    sm.material = bpy.data.materials['en_' + o.material_slots[s].material.name]

                    if s in mis:
                        sm.material.visuite_envi[0].export = True
                    if md.con_type in dcdict:
                        sm.material.diffuse_color = dcdict[mct]
                    if mct not in ('None', 'Shading', 'Aperture', 'Window'):
                        uv = retuval(md, context)
                        sm.material.visuite_envi[0].material_uv = '{:.3f}'.format(uv)

            for poly in en_o.data.polygons:
                m = en_o.data.materials[poly.material_index]
                md = VISUITE_Material_Envi.datablock(m)
                if (poly.area < 0.001 or md is None or md.con_type == 'None'):
                    poly.select = True

            selmesh('delf')

            for edge in en_o.data.edges:
                if edge.is_loose:
                    edge.select = True
                    for vi in edge.vertices:
                        en_o.data.vertices[vi].select = True
            selmesh('delv')
#            selmesh('dele')

            bm = bmesh.new()
            bm.from_mesh(en_o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)

            geom = [e for e in bm.edges if not e.link_faces]
            geom.extend([v for v in bm.verts if not v.link_faces])

            bmesh.ops.delete(bm, geom=geom)

            if all([e.is_manifold for e in bm.edges]):
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            else:
                reversefaces = []
                for face in bm.faces:
                    m = o.data.materials[face.material_index]
                    md = VISUITE_Material_Envi.datablock(m)
                    if (md.con_type in ('Wall', 'Window', 'Floor', 'Roof', 'Door') and
                            (face.calc_center_bounds()).dot(face.normal) < 0):
                        reversefaces.append(face)

                bmesh.ops.reverse_faces(bm, faces=reversefaces)

            bmesh.ops.split_edges(bm, edges=bm.edges)
            bmesh.ops.dissolve_limit(bm, angle_limit=0.01, verts=bm.verts)
            bm.faces.ensure_lookup_table()

            regfaces = []
            for face in bm.faces:
                m = o.data.materials[face.material_index]
                md = VISUITE_Material_Envi.datablock(m)
                if not any((md.boundary, md.afsurface)):
                    regfaces.append(face)

            bmesh.ops.connect_verts_nonplanar(bm, angle_limit=0.01, faces=regfaces)
            bmesh.ops.connect_verts_concave(bm, faces=regfaces)

            faces = []
            for face in bm.faces:
                m = o.data.materials[face.material_index]
                md = VISUITE_Material_Envi.datablock(m)
                if (md and md.con_type in ('Window', 'Door') and
                        ['{:.4f}'.format(fl.calc_angle()) for fl in face.loops] != ['1.5708'] * 4):
                    faces.append(face)

            bmesh.ops.triangulate(bm, faces=faces)
            bm.to_mesh(en_o.data)
            bm.free()

            o['children'] = en_o.name
            linklist = []
            for link in enng.links:
                if link.from_socket.bl_idname in ('EnViBoundSocket', 'EnViSFlowSocket', 'EnViSSFlowSocket'):
                    linklist.append([link.from_socket.node.name, link.from_socket.name,
                                    link.to_socket.node.name, link.to_socket.name])
                    enng.links.remove(link)

            if en_o.name not in [node.zone for node in enng.nodes if hasattr(node, 'zone')]:
                enng.nodes.new(type=ezdict[d.type]).zone = en_o.name
            else:
                for node in enng.nodes:
                    if hasattr(node, 'zone') and node.zone == en_o.name:
                        node.zupdate(bpy.context)

            for node in enng.nodes:
                if hasattr(node, 'emszone') and node.emszone == en_o.name:
                    node.zupdate(bpy.context)

            for ll in linklist:
                try:
                    enng.links.new(enng.nodes[ll[0]].outputs[ll[1]], enng.nodes[ll[2]].inputs[ll[3]])
                except:
                    pass

            for node in enng.nodes:
                if hasattr(node, 'zone') and node.zone == en_o.name:
                    node.uvsockupdate()
            mats = [VISUITE_Material_Envi.datablock(m) for m in enomats if VISUITE_Material_Envi.datablock(m)]
            if any([mat.afsurface for mat in mats]):
                enng['enviparams']['afn'] = 1
                if 'Control' not in [node.bl_label for node in enng.nodes]:
                    enng.nodes.new(type='AFNCon')
                    enng.use_fake_user = 1

            bpy.data.scenes[0].layers[0:2] = True, False
            o.select = True
            scene.objects.active = o
        # Shading
        elif d.type == '1':
            selobj(scene, o)
            bpy.ops.object.duplicate()
            en_o = scene.objects.active
            en_o.name = 'en_' + o.name
            selmesh('rd')
            selmesh('mc')
            selmesh('mp')

            shadmat = bpy.data.materials.get('en_shading')

            if not shadmat:
                shadmat = bpy.data.materials.new('en_shading')
                md = shadmat.visuite_envi.add()
                md.con_type = 'Shading'

            if not en_o.material_slots:
                bpy.ops.object.material_slot_add()
            else:
                while len(en_o.material_slots) > 1:
                    bpy.ops.object.material_slot_remove()

            en_o.material_slots[0].material = shadmat
            en_o.material_slots[0].material.diffuse_color = (1, 0, 0)
            en_o.layers[1], en_o.layers[0] = True, False


def enpolymatexport(context, exp_op, node, locnode, em, ec):
    scene = context.scene

    for frame in range(scene['enparams']['fs'], scene['enparams']['fe'] + 1):
        scene.update()
        scene.frame_set(frame)
        en_idf = open(os.path.join(scene['viparams']['newdir'], 'in{}.idf'.format(frame)), 'w')
        enng = [ng for ng in bpy.data.node_groups if ng.bl_label == 'EnVi Network'][0]
        badnodes = [node for node in enng.nodes if node.use_custom_color]
        for node in badnodes:
            node.hide = 0
            exp_op.report({'ERROR'}, 'Bad {} node in the EnVi network. \
                            Delete the node if not needed or make valid connections'.format(node.name))
            return
        en_idf.write("!- Blender -> EnergyPlus\n!- Using the EnVi export scripts\n!-" +
            " Author: Ryan Southall\n!- Date: {}\n\nVERSION,{};\n\n".format(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                scene['enparams']['epversion'])
            )

        params = ('Name',
            'North Axis (deg)',
            'Terrain',
            'Loads Convergence Tolerance Value',
            'Temperature Convergence Tolerance Value (deltaC)',
            'Solar Distribution',
            'Maximum Number of Warmup Days(from MLC TCM)')

        paramvs = (node.loc,
            '0.00',
            ("City", "Urban", "Suburbs", "Country", "Ocean")[int(node.terrain)],
            '0.004',
            '0.4',
            # handle non-convex zones with 
            'FullInteriorAndExteriorWithReflections',
            '15')

        en_idf.write(epentry('Building', params, paramvs))

        params = ('Time Step in Hours',
            'Algorithm',
            'Algorithm',
            'Default frequency of calculation',
            'no zone sizing, system sizing, plant sizing, no design day, use weather file')

        paramvs = ('Timestep, {}'.format(node.timesteps),
            'SurfaceConvectionAlgorithm:Inside, TARP',
            'SurfaceConvectionAlgorithm:Outside, TARP',
            'ShadowCalculation, AverageOverDaysInFrequency, 10',
            'SimulationControl, No,No,No,No,Yes')

        for ppair in zip(params, paramvs):
            en_idf.write(epentry('', [ppair[0]], [ppair[1]]) + ('', '\n\n')[ppair[0] == params[-1]])

        en_idf.write('HeatBalanceAlgorithm, ConductionTransferFunction;\n\n')

        params = ('Name',
            'Begin Month',
            'Begin Day',
            'End Month',
            'End Day',
            'Day of Week for Start Day',
            'Use Weather File Holidays and Special Days',
            'Use Weather File Daylight Saving Period',
            'Apply Weekend Holiday Rule',
            'Use Weather File Rain Indicators',
            'Use Weather File Snow Indicators',
            'Number of Times Runperiod to be Repeated')

        paramvs = (node.loc,
            node.sdate.month,
            node.sdate.day,
            node.edate.month,
            node.edate.day,
            "UseWeatherFile",
            "Yes",
            "Yes",
            "No",
            "Yes",
            "Yes",
            "1")

        en_idf.write(epentry('RunPeriod', params, paramvs))
        en_idf.write("!-   ===========  ALL OBJECTS IN CLASS: MATERIAL & CONSTRUCTIONS ===========\n\n")
        matcount, matname = [], []

        envimats = [(mat.name, mat.visuite_envi[0]) for mat in bpy.data.materials
                    if VISUITE_Material_Envi.datablock(mat) and mat.visuite_envi[0].con_type != "None"]

        if 'Window' in [md.con_type for mn, md in envimats] or 'Door' in [md.con_type for mn, md in envimats]:
            params = ('Name', 'Roughness', 'Thickness (m)', 'Conductivity (W/m-K)',
                'Density (kg/m3)', 'Specific Heat (J/kg-K)',
                'Thermal Absorptance', 'Solar Absorptance',
                'Visible Absorptance', 'Name', 'Outside Layer')
            paramvs = ('Wood frame', 'Rough', '0.12', '0.1', '1400', '1000', '0.9', '0.6', '0.6', 'Frame', 'Wood frame')
            en_idf.write(epentry('Material', params[:-2], paramvs[:-2]))
            en_idf.write(epentry('Construction', params[-2:], paramvs[-2:]))

        for mat_name, md in [(mat_name, md) for mat_name, md in envimats if md.export is True]:
            conlist, is_pcm = [], 0

            if md.con_type not in ('Shading', 'Aperture'):

                if len(md.layers) % 2 and md.con_type == 'Window':
                    exp_op.report({'ERROR'}, 'Wrong number of layers specified for the {} window construction'.format(
                        mat_name
                        ))
                    return

                for l, layer in enumerate(md.layers):

                    lmat = layer.export_name
                    if md.con_type in ('Wall', 'Floor', 'Roof', 'Ceiling', 'Door'):

                        params = [
                            str(getattr(layer, "export_" + prop)) for prop in
                            ["rough", "tc", "rho", "shc", "tab", "sab", "vab"]
                            ]

                        em.omat_write(en_idf,
                            lmat + "-" + str(matcount.count(lmat.upper())),
                            params,
                            layer.export_thi / 1000)

                        if lmat in em.pcm_dat:
                            em.pcmmat_write(
                                en_idf,
                                '{}-{}'.format(lmat, matcount.count(lmat.upper())),
                                [layer.export_tctc, layer.export_tempemps])
                            is_pcm = 1

                    elif md.con_type == "Window":
                        if not l % 2:
                            params = ['Glazing']
                            params.extend(
                                [str(getattr(layer, "export_" + prop)) for prop in
                                    ["odt", "sds", "thi", "stn", "fsn", "bsn", "vtn",
                                    "fvrn", "bvrn", "itn", "fie", "bie", "tc", "sdiff"]
                                ])

                            if len(md.layers) < l + 1:
                                params[-1] = 0

                            em.tmat_write(
                                en_idf,
                                '{}-{}'.format(lmat, matcount.count(lmat.upper())),
                                params,
                                layer.export_thi / 1000)
                        else:
                            params = ("Gas", layer.export_wgas)
                            em.gmat_write(
                                en_idf,
                                lmat + "-" + str(matcount.count(lmat.upper())),
                                params,
                                layer.export_thi / 1000)

                    conlist.append('{}-{}'.format(lmat, matcount.count(lmat.upper())))
                    matname.append('{}-{}'.format(lmat, matcount.count(lmat.upper())))
                    matcount.append(lmat.upper())

                params, paramvs = ['Name'], [mat_name]
                for i, mn in enumerate(conlist):
                    params.append('Layer {}'.format(i))
                    paramvs.append(mn)
                en_idf.write(epentry('Construction', params, paramvs))

                if is_pcm:

                    pcmparams = ('Name',
                        'Algorithm',
                        'Construction Name')

                    pcmparamsv = ('{} CondFD override'.format(mat_name),
                        'ConductionFiniteDifference',
                        mat_name)

                    en_idf.write(epentry(
                        'SurfaceProperty:HeatTransferAlgorithm:Construction',
                        pcmparams,
                        pcmparamsv))

        em.namedict = {}
        em.thickdict = {}

        en_idf.write("!-   ===========  ALL OBJECTS IN CLASS: ZONES ===========\n\n")

        enviobjs = []
        for o in context.scene.objects:
            d = VISUITE_Object_Envi.datablock(o)
            if d and o.layers[1] and o.type == 'MESH':
                enviobjs.append((o, d))

        for o, d in enviobjs:
            if d.type in ('0', '2'):
                params = ('Name',
                    'Direction of Relative North (deg)',
                    'X Origin (m)',
                    'Y Origin (m)',
                    'Z Origin (m)',
                    'Type',
                    'Multiplier',
                    'Ceiling Height (m)',
                    'Volume (m3)',
                    'Floor Area (m2)',
                    'Zone Inside Convection Algorithm',
                    'Zone Outside Convection Algorithm',
                    'Part of Total Floor Area')

                paramvs = (o.name,
                    0,
                    0,
                    0,
                    0,
                    1,
                    1,
                    'autocalculate',
                    'autocalculate',
                    'autocalculate',
                    caidict[d.ica],
                    caodict[d.oca],
                    'Yes')

                en_idf.write(epentry('Zone', params, paramvs))

        params = ('Starting Vertex Position',
            'Vertex Entry Direction',
            'Coordinate System')
        paramvs = ('UpperRightCorner',
            'Counterclockwise',
            'World')

        en_idf.write(epentry('GlobalGeometryRules', params, paramvs))

        en_idf.write("!-   ===========  ALL OBJECTS IN CLASS: SURFACE DEFINITIONS ===========\n\n")

        wfrparams = ['Name',
            'Surface Type',
            'Construction Name',
            'Zone Name',
            'Outside Boundary Condition',
            'Outside Boundary Condition Object',
            'Sun Exposure',
            'Wind Exposure',
            'View Factor to Ground',
            'Number of Vertices']

        for o, d in enviobjs:

            me = o.to_mesh(scene, True, 'PREVIEW')
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.transform(o.matrix_world)
            bpy.data.meshes.remove(me)

            for face in bm.faces:

                mat = o.data.materials[face.material_index]
                md = VISUITE_Material_Envi.datablock(mat)
                if md:
                    vcos = [v.co for v in face.verts]
                    (obc, obco, se, we) = boundpoly(o, mat, md, face, enng)
                    if md.con_type in ('Wall', "Floor", "Roof", "Ceiling"):

                        params = list(wfrparams)
                        params += ["X,Y,Z ==> Vertex {} (m)".format(v.index) for v in face.verts]

                        paramvs = [
                            '{}_{}'.format(o.name, face.index),
                            md.con_type,
                            mat.name,
                            o.name,
                            obc,
                            obco,
                            se,
                            we,
                            'autocalculate',
                            len(face.verts)]

                        paramvs += ["  {0[0]:.4f}, {0[1]:.4f}, {0[2]:.4f}".format(vco) for vco in vcos]

                        en_idf.write(epentry('BuildingSurface:Detailed', params, paramvs))

                    elif md.con_type in ('Door', 'Window'):
                        if len(face.verts) > 4:
                            exp_op.report({'ERROR'}, 'Window/door in {} has more than 4 vertices'.format(o.name))

                        xav, yav, zav = face.calc_center_median()

                        params = list(wfrparams)
                        params += ["X,Y,Z ==> Vertex {} (m)".format(v.index) for v in face.verts]

                        paramvs = ['{}_{}'.format(o.name, face.index),
                            'Wall',
                            'Frame',
                            o.name,
                            obc,
                            obco,
                            se,
                            we,
                            'autocalculate',
                            len(face.verts)]

                        paramvs += ["  {0[0]:.4f}, {0[1]:.4f}, {0[2]:.4f}".format(vco) for vco in vcos]

                        en_idf.write(epentry('BuildingSurface:Detailed', params, paramvs))

                        obound = ('win-', 'door-')[md.con_type == 'Door'] + obco if obco else obco

                        params = ['Name',
                            'Surface Type',
                            'Construction Name',
                            'Building Surface Name',
                            'Outside Boundary Condition Object',
                            'View Factor to Ground',
                            'Shading Control Name',
                            'Frame and Divider Name',
                            'Multiplier',
                            'Number of Vertices']

                        params += ["X,Y,Z ==> Vertex {} (m)".format(v.index) for v in face.verts]

                        paramvs = [('win-', 'door-')[md.con_type == 'Door'] + '{}_{}'.format(o.name, face.index),
                            md.con_type,
                            mat.name, '{}_{}'.format(o.name, face.index),
                            obound,
                            'autocalculate',
                            '',
                            '',
                            '1',
                            len(face.verts)]

                        paramvs += ["  {0[0]:.4f}, {0[1]:.4f}, {0[2]:.4f}".format(
                            (xav + (vco[0] - xav) * 0.95,
                             yav + (vco[1] - yav) * 0.95,
                             zav + (vco[2] - zav) * 0.95))
                             for vco in vcos]

                        en_idf.write(epentry('FenestrationSurface:Detailed', params, paramvs))

                    elif md.con_type == 'Shading' or d.type == '1':
                        params = ['Name', 'Transmittance Schedule Name', 'Number of Vertices']
                        params += ['X,Y,Z ==> Vertex {} (m)'.format(v.index) for v in face.verts]
                        paramvs = ['{}_{}'.format(o.name, face.index), '', len(face.verts)]
                        paramvs += ['{0[0]:.4f}, {0[1]:.4f}, {0[2]:.4f}'.format(vco) for vco in vcos]
                        en_idf.write(epentry('Shading:Building:Detailed', params, paramvs))
            bm.free()

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: SCHEDULES ===========\n\n")
        params = ('Name', 'Lower Limit Value', 'Upper Limit Value', 'Numeric Type', 'Unit Type')
        paramvs = ("Temperature", -60, 200, "CONTINUOUS", "Temperature")
        en_idf.write(epentry('ScheduleTypeLimits', params, paramvs))
        params = ('Name', 'Lower Limit Value', 'Upper Limit Value', 'Numeric Type')
        paramvs = ("Control Type", 0, 4, "DISCRETE")
        en_idf.write(epentry('ScheduleTypeLimits', params, paramvs))
        params = ('Name', 'Lower Limit Value', 'Upper Limit Value', 'Numeric Type')
        paramvs = ("Fraction", 0, 1, "CONTINUOUS")
        en_idf.write(epentry('ScheduleTypeLimits', params, paramvs))
        params = ['Name']
        paramvs = ["Any Number"]
        en_idf.write(epentry('ScheduleTypeLimits', params, paramvs))
        en_idf.write(epschedwrite(
                'Default outdoor CO2 levels 400 ppm',
                'Any number',
                ['Through: 12/31'],
                [['For: Alldays']],
                [[[['Until: 24:00,{}'.format('400')]]]]))

        enviobjects = [o for o in context.scene.objects if VISUITE_Object_Envi.datablock(o)]
        zonenames = [o.name for o in enviobjects if o.layers[1] is True and o.visuite_envi[0].type == '0']
        tcnames = [o.name for o in enviobjects if o.layers[1] is True and o.visuite_envi[0].type == '2']

        context.scene['viparams']['hvactemplate'] = 0
        zonenodes = [n for n in enng.nodes if hasattr(n, 'zone') and n.zone in zonenames]
        tcnodes = [n for n in enng.nodes if hasattr(n, 'zone') and n.zone in tcnames]

        for zn in zonenodes:
            for schedtype in ('VASchedule', 'TSPSchedule', 'HVAC', 'Occupancy', 'Equipment', 'Infiltration'):
                if schedtype == 'HVAC' and zn.inputs[schedtype].links:
                    en_idf.write(zn.inputs[schedtype].links[0].from_node.eptcwrite(zn.zone))
                    try:
                        en_idf.write(
                            zn.inputs[schedtype].links[0].from_node.inputs['Schedule'].links[0].from_node.epwrite(
                                zn.zone + '_hvacsched',
                                'Fraction'))
                    except:
                        en_idf.write(epschedwrite(
                            zn.zone + '_hvacsched',
                            'Fraction',
                            ['Through: 12/31'],
                            [['For: Alldays']],
                            [[[['Until: 24:00, 1']]]]))

                    hsdict = {'HSchedule': '_htspsched',
                              'CSchedule': '_ctspsched'}
                    tvaldict = {'HSchedule': zn.inputs[schedtype].links[0].from_node.envi_htsp,
                                'CSchedule': zn.inputs[schedtype].links[0].from_node.envi_ctsp}
                    for sschedtype in hsdict:
                        if zn.inputs[schedtype].links[0].from_node.inputs[sschedtype].links:
                            en_idf.write(
                                zn.inputs[schedtype].links[0].from_node.inputs[sschedtype].links[0].from_node.epwrite(
                                    zn.zone + hsdict[sschedtype],
                                    'Temperature'))
                        else:
                            en_idf.write(epschedwrite(
                                zn.zone + hsdict[sschedtype],
                                'Temperature',
                                ['Through: 12/31'],
                                [['For: Alldays']],
                                [[[['Until: 24:00,{}'.format(tvaldict[sschedtype])]]]]))

                elif schedtype == 'Occupancy' and zn.inputs[schedtype].links:
                    osdict = {'OSchedule': '_occsched',
                            'ASchedule': '_actsched',
                            'WSchedule': '_wesched',
                            'VSchedule': '_avsched',
                            'CSchedule': '_closched'}
                    ovaldict = {'OSchedule': 1, 'ASchedule': zn.inputs[schedtype].links[0].from_node.envi_occwatts,
                                'WSchedule': zn.inputs[schedtype].links[0].from_node.envi_weff,
                                'VSchedule': zn.inputs[schedtype].links[0].from_node.envi_airv,
                                'CSchedule': zn.inputs[schedtype].links[0].from_node.envi_cloth}
                    for sschedtype in osdict:
                        svariant = 'Fraction' if sschedtype == 'OSchedule' else 'Any Number'
                        if zn.inputs[schedtype].links[0].from_node.inputs[sschedtype].links:
                            en_idf.write(
                                zn.inputs[schedtype].links[0].from_node.inputs[sschedtype].links[0].from_node.epwrite(
                                    zn.zone + osdict[sschedtype],
                                    svariant))
                        else:
                            en_idf.write(epschedwrite(
                                zn.zone + osdict[sschedtype],
                                svariant,
                                ['Through: 12/31'],
                                [['For: Alldays']],
                                [[[['Until: 24:00,{:.3f}'.format(ovaldict[sschedtype])]]]]))

                elif schedtype == 'Equipment' and zn.inputs[schedtype].links:
                    if not zn.inputs[schedtype].links[0].from_node.inputs['Schedule'].links:
                        en_idf.write(epschedwrite(
                            zn.zone + '_eqsched',
                            'Fraction',
                            ['Through: 12/31'],
                            [['For: Alldays']],
                            [[[['Until: 24:00,1']]]]))
                    else:
                        en_idf.write(
                            zn.inputs[schedtype].links[0].from_node.inputs['Schedule'].links[0].from_node.epwrite(
                                zn.zone + '_eqsched',
                                'Fraction'))

                elif schedtype == 'Infiltration' and zn.inputs[schedtype].links:
                    if not zn.inputs[schedtype].links[0].from_node.inputs['Schedule'].links:
                        en_idf.write(epschedwrite(
                            zn.zone + '_infsched',
                            'Fraction',
                            ['Through: 12/31'],
                            [['For: Alldays']],
                            [[[['Until: 24:00,{}'.format(1)]]]]))
                    else:
                        en_idf.write(
                            zn.inputs[schedtype].links[0].from_node.inputs['Schedule'].links[0].from_node.epwrite(
                                zn.zone + '_infsched',
                                'Fraction'))

                elif schedtype == 'VASchedule' and zn.inputs[schedtype].links:
                    en_idf.write(
                        zn.inputs[schedtype].links[0].from_node.epwrite(
                            zn.zone + '_vasched',
                            'Fraction'))

                elif schedtype == 'TSPSchedule' and zn.inputs[schedtype].links:
                    en_idf.write(
                        zn.inputs[schedtype].links[0].from_node.epwrite(
                            zn.zone + '_tspsched',
                            'Temperature'))

        ssafnodes = [enode for enode in enng.nodes if enode.bl_idname == 'EnViSSFlow']

        for zn in ssafnodes:
            for schedtype in ('VASchedule', 'TSPSchedule'):
                if schedtype == 'VASchedule' and zn.inputs[schedtype].links:
                    en_idf.write(
                        zn.inputs[schedtype].links[0].from_node.epwrite(
                            '{}_vasched'.format(zn.name),
                            'Fraction'))

                elif schedtype == 'TSPSchedule' and zn.inputs[schedtype].links:
                    en_idf.write(
                        zn.inputs[schedtype].links[0].from_node.epwrite(
                            '{}_tspsched'.format(zn.name),
                            'Temperature'))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: THERMOSTSTATS ===========\n\n")
        for zn in zonenodes:
            for hvaclink in zn.inputs['HVAC'].links:
                en_idf.write(hvaclink.from_node.eptspwrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: EQUIPMENT ===========\n\n")
        for zn in zonenodes:
            for hvaclink in zn.inputs['HVAC'].links:
                hvaczone = hvaclink.from_node
                if not hvaczone.envi_hvact:
                    en_idf.write(zn.inputs['HVAC'].links[0].from_node.epewrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: HVAC ===========\n\n")
        for zn in zonenodes:
            for hvaclink in zn.inputs['HVAC'].links:
                hvacnode = hvaclink.from_node
                if hvacnode.envi_hvact:
                    en_idf.write(hvacnode.hvactwrite(zn.zone))
                else:
                    en_idf.write(hvacnode.ephwrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: OCCUPANCY ===========\n\n")
        for zn in zonenodes:
            for occlink in zn.inputs['Occupancy'].links:
                en_idf.write(occlink.from_node.epwrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: OTHER EQUIPMENT ===========\n\n")
        for zn in zonenodes:
            for eqlink in zn.inputs['Equipment'].links:
                en_idf.write(eqlink.from_node.oewrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: CONTAMINANTS ===========\n\n")
        zacb = 0
        for zn in zonenodes:
            if not zacb:
                for occlink in zn.inputs['Occupancy'].links:
                    if occlink.from_node.envi_co2 and occlink.from_node.envi_comfort:
                        params = ('Carbon Dioxide Concentration',
                                'Outdoor Carbon Dioxide Schedule Name',
                                'Generic Contaminant Concentration',
                                'Outdoor Generic Contaminant Schedule Name')
                        paramvs = ('Yes', 'Default outdoor CO2 levels 400 ppm', 'No', '')
                        en_idf.write(epentry('ZoneAirContaminantBalance', params, paramvs))
                        zacb = 1
                        break

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: INFILTRATION ===========\n\n")
        for zn in zonenodes:
            for inflink in zn.inputs['Infiltration'].links:
                en_idf.write(inflink.from_node.epwrite(zn.zone))

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: TH ===========\n\n")
        for zn in tcnodes:
            if zn.bl_idname == 'EnViTC':
                en_idf.write(zn.epwrite())

        en_idf.write("\n!-   ===========  ALL OBJECTS IN CLASS: AIRFLOW NETWORK ===========\n\n")

        if enng and enng['enviparams']['afn']:
            writeafn(exp_op, en_idf, enng)

        en_idf.write("!-   ===========  ALL OBJECTS IN CLASS: EMS ===========\n\n")
        emsprognodes = [pn for pn in enng.nodes if pn.bl_idname == 'EnViProg' and not pn.use_custom_color]
        for prognode in emsprognodes:
            en_idf.write(prognode.epwrite())

        en_idf.write("!-   ===========  ALL OBJECTS IN CLASS: REPORT VARIABLE ===========\n\n")
        afn = enng['enviparams']['afn']
        epentrydict = {"Output:Variable,*,Zone Air Temperature,hourly;\n": node.restt,
           "Output:Variable,*,Zone Air System Sensible Heating Rate,hourly;\n": node.restwh,
           "Output:Variable,*,Zone Air System Sensible Cooling Rate,hourly;\n": node.restwc,
           "Output:Variable,*,Zone Ideal Loads Supply Air Sensible Heating Rate, hourly;\n": node.ressah,
           "Output:Variable,*,Zone Ideal Loads Heat Recovery Sensible Heating Rate, hourly;\n": node.reshrhw,
           "Output:Variable,*,Zone Ideal Loads Supply Air Sensible Cooling Rate,hourly;\n": node.ressac,
           "Output:Variable,*,Zone Thermal Comfort Fanger Model PMV,hourly;\n": node.rescpm,
           "Output:Variable,*,Zone Thermal Comfort Fanger Model PPD,hourly;\n": node.rescpp,
           "Output:Variable,*,AFN Zone Infiltration Volume, hourly;\n": node.resim and afn,
           "Output:Variable,*,AFN Zone Infiltration Air Change Rate, hourly;\n": node.resiach and afn,
           "Output:Variable,*,Zone Infiltration Current Density Volume [m3]": node.resim and not afn,
           "Output:Variable,*,Zone Infiltration Air Change Rate, hourly;\n": node.resiach and not afn,
           "Output:Variable,*,Zone Windows Total Transmitted Solar Radiation Rate,hourly;\n": node.reswsg,
           "Output:Variable,*,AFN Node CO2 Concentration,hourly;\n": node.resco2 and afn,
           "Output:Variable,*,Zone Air CO2 Concentration,hourly;\n": node.resco2 and not afn,
           "Output:Variable,*,Zone Mean Radiant Temperature,hourly;\n": node.resmrt,
           "Output:Variable,*,Zone People Occupant Count,hourly;\n": node.resocc,
           "Output:Variable,*,Zone Air Relative Humidity,hourly;\n": node.resh,
           "Output:Variable,*,Zone Air Heat Balance Surface Convection Rate, hourly;\n": node.resfhb,
           "Output:Variable,*,Zone Thermal Chimney Current Density Air Volume Flow Rate,hourly;\n": node.restcvf,
           "Output:Variable,*,Zone Thermal Chimney Mass Flow Rate,hourly;\n": node.restcmf,
           "Output:Variable,*,Zone Thermal Chimney Outlet Temperature,hourly;\n": node.restcot,
           "Output:Variable,*,Zone Thermal Chimney Heat Loss Energy,hourly;\n": node.restchl,
           "Output:Variable,*,Zone Thermal Chimney Heat Gain Energy,hourly;\n": node.restchg,
           "Output:Variable,*,Zone Thermal Chimney Volume,hourly;\n": node.restcv,
           "Output:Variable,*,Zone Thermal Chimney Mass,hourly;\n": node.restcm}

        for amb in ("Output:Variable,*,Site Outdoor Air Drybulb Temperature,Hourly;\n",
                    "Output:Variable,*,Site Wind Speed,Hourly;\n",
                    "Output:Variable,*,Site Wind Direction,Hourly;\n",
                    "Output:Variable,*,Site Outdoor Air Relative Humidity,hourly;\n",
                    "Output:Variable,*,Site Direct Solar Radiation Rate per Area,hourly;\n",
                    "Output:Variable,*,Site Diffuse Solar Radiation Rate per Area,hourly;\n"):
            en_idf.write(amb)

        for ep in epentrydict:
            if epentrydict[ep]:
                en_idf.write(ep)

        if node.resl12ms:
            for cnode in [cnode for cnode in enng.nodes if cnode.bl_idname == 'EnViSFlow']:
                for sno in cnode['sname']:
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 1 to Node 2 Volume Flow Rate,hourly;\n".format(sno))
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 2 to Node 1 Volume Flow Rate,hourly;\n".format(sno))
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 1 to Node 2 Pressure Difference,hourly;\n".format(sno))
            for snode in [snode for snode in enng.nodes if snode.bl_idname == 'EnViSSFlow']:
                for sno in snode['sname']:
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 1 to Node 2 Volume Flow Rate,hourly;\n".format(sno))
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 2 to Node 1 Volume Flow Rate,hourly;\n".format(sno))
                    en_idf.write(
                        "Output:Variable,{0},AFN Linkage Node 1 to Node 2 Pressure Difference,hourly;\n".format(sno))
        if node.reslof is True:
            for snode in [snode for snode in enng.nodes if snode.bl_idname == 'EnViSSFlow']:
                if snode.linkmenu in ('SO', 'DO', 'HO'):
                    for sno in snode['sname']:
                        en_idf.write(
                            "Output:Variable," +
                            "{},AFN Surface Venting Window or Door Opening Factor,hourly;\n".format(sno))

        en_idf.write("Output:Table:SummaryReports,\
        AllSummary;              !- Report 1 Name")
        en_idf.close()

        if scene['enparams'].get('hvactemplate'):
            os.chdir(scene['viparams']['newdir'])
            ehtempcmd = "ExpandObjects {}".format(os.path.join(scene['viparams']['newdir'], 'in.idf'))
            subprocess.call(ehtempcmd.split())
            shutil.copyfile(
                os.path.join(scene['viparams']['newdir'], 'expanded.idf'),
                os.path.join(scene['viparams']['newdir'], 'in.idf'))

        if 'in{}.idf'.format(frame) not in [im.name for im in bpy.data.texts]:
            bpy.data.texts.load(os.path.join(scene['viparams']['newdir'], 'in{}.idf'.format(frame)))
        else:
            bpy.data.texts['in{}.idf'.format(frame)].filepath = \
                os.path.join(scene['viparams']['newdir'], 'in{}.idf'.format(frame))


def writeafn(exp_op, en_idf, enng):
    if ([enode for enode in enng.nodes if enode.bl_idname == 'AFNCon'] and not
            [enode for enode in enng.nodes if enode.bl_idname == 'EnViZone']):
        [enng.nodes.remove(enode) for enode in enng.nodes if enode.bl_idname == 'AFNCon']
    for connode in [enode for enode in enng.nodes if enode.bl_idname == 'AFNCon']:
        en_idf.write(connode.epwrite(exp_op, enng))
    for crnode in [enode for enode in enng.nodes if enode.bl_idname == 'EnViCrRef']:
        en_idf.write(crnode.epwrite())
        enng['enviparams']['crref'] = 1
    extnodes = [enode for enode in enng.nodes if enode.bl_idname == 'EnViExt']
    zonenodes = [enode for enode in enng.nodes if enode.bl_idname == 'EnViZone']
    ssafnodes = [enode for enode in enng.nodes if enode.bl_idname == 'EnViSSFlow']
    safnodes = [enode for enode in enng.nodes if enode.bl_idname == 'EnViSFlow']

    if enng['enviparams']['wpca'] == 1:
        for extnode in extnodes:
            en_idf.write(extnode.epwrite(enng))
    for enode in zonenodes:
        en_idf.write(enode.epwrite())
    for enode in ssafnodes + safnodes:
        en_idf.write(enode.epwrite(exp_op, enng))


bpy.utils.register_class(VISUITE_MT_envi_preset)
bpy.utils.register_class(VISUITE_OP_envi_preset)
bpy.utils.register_class(VISUITE_Material_EnviLayer)
bpy.utils.register_class(VISUITE_Material_Envi)
Material.visuite_envi = CollectionProperty(type=VISUITE_Material_Envi, description="Envi material", name="Envi")
bpy.utils.register_class(VISUITE_OP_envi_material_add)
bpy.utils.register_class(VISUITE_OP_envi_material_remove)
bpy.utils.register_class(VISUITE_OP_envi_material_layer_add)
bpy.utils.register_class(VISUITE_OP_envi_material_layer_remove)
bpy.utils.register_class(VISUITE_PT_envi_material)
bpy.utils.register_class(VISUITE_Object_Envi)
Object.visuite_envi = CollectionProperty(type=VISUITE_Object_Envi, description="Envi Object", name="Envi")
bpy.utils.register_class(VISUITE_OP_envi_object_add)
bpy.utils.register_class(VISUITE_OP_envi_object_remove)
bpy.utils.register_class(VISUITE_PT_envi_object)
