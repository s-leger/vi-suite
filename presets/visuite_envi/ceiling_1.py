import bpy
d = bpy.context.active_object.active_material.visuite_envi[0]

d.afsurface = False
d.aperture = '0'
d.boundary = False
d.con_type = 'Ceiling'
d.export = False
d.layers.clear()
item_sub_1 = d.layers.add()
item_sub_1.con_type = 'Ceiling'
item_sub_1.envi_index = 0
item_sub_1.envi_layer = '1'
item_sub_1.envi_material_group = '5'
item_sub_1.envi_material_name = 'Chipboard'
item_sub_1.export_bie = 0.8399999737739563
item_sub_1.export_bsn = 0.07500000298023224
item_sub_1.export_bvrn = 0.07999999821186066
item_sub_1.export_dcf = 0.0
item_sub_1.export_fie = 0.8399999737739563
item_sub_1.export_fsn = 0.07500000298023224
item_sub_1.export_fvrn = 0.07999999821186066
item_sub_1.export_itn = 0.0
item_sub_1.export_name = 'Chipboard'
item_sub_1.export_odt = 'SpectralAverage'
item_sub_1.export_rho = 800.0
item_sub_1.export_rough = 'MediumSmooth'
item_sub_1.export_sab = 0.6499999761581421
item_sub_1.export_sdiff = False
item_sub_1.export_sds = '0'
item_sub_1.export_shc = 2093.0
item_sub_1.export_stn = 0.8999999761581421
item_sub_1.export_tab = 0.9100000262260437
item_sub_1.export_tc = 0.15000000596046448
item_sub_1.export_tctc = 0.0
item_sub_1.export_tempsemps = ''
item_sub_1.export_thi = 25.0
item_sub_1.export_vab = 0.6499999761581421
item_sub_1.export_vtn = 0.8999999761581421
item_sub_1.export_wgas = 'Air'
item_sub_1.name = ''
item_sub_1 = d.layers.add()
item_sub_1.con_type = 'Ceiling'
item_sub_1.envi_index = 1
item_sub_1.envi_layer = '1'
item_sub_1.envi_material_group = '7'
item_sub_1.envi_material_name = 'EPS'
item_sub_1.export_bie = 0.8399999737739563
item_sub_1.export_bsn = 0.07500000298023224
item_sub_1.export_bvrn = 0.07999999821186066
item_sub_1.export_dcf = 0.0
item_sub_1.export_fie = 0.8399999737739563
item_sub_1.export_fsn = 0.07500000298023224
item_sub_1.export_fvrn = 0.07999999821186066
item_sub_1.export_itn = 0.0
item_sub_1.export_name = 'EPS'
item_sub_1.export_odt = 'SpectralAverage'
item_sub_1.export_rho = 15.0
item_sub_1.export_rough = 'MediumSmooth'
item_sub_1.export_sab = 0.699999988079071
item_sub_1.export_sdiff = False
item_sub_1.export_sds = '0'
item_sub_1.export_shc = 1000.0
item_sub_1.export_stn = 0.8999999761581421
item_sub_1.export_tab = 0.8999999761581421
item_sub_1.export_tc = 0.03500000014901161
item_sub_1.export_tctc = 0.0
item_sub_1.export_tempsemps = ''
item_sub_1.export_thi = 100.0
item_sub_1.export_vab = 0.699999988079071
item_sub_1.export_vtn = 0.8999999761581421
item_sub_1.export_wgas = 'Air'
item_sub_1.name = ''
item_sub_1 = d.layers.add()
item_sub_1.con_type = 'Ceiling'
item_sub_1.envi_index = 2
item_sub_1.envi_layer = '1'
item_sub_1.envi_material_group = '1'
item_sub_1.envi_material_name = 'Plaster board'
item_sub_1.export_bie = 0.8399999737739563
item_sub_1.export_bsn = 0.07500000298023224
item_sub_1.export_bvrn = 0.07999999821186066
item_sub_1.export_dcf = 0.0
item_sub_1.export_fie = 0.8399999737739563
item_sub_1.export_fsn = 0.07500000298023224
item_sub_1.export_fvrn = 0.07999999821186066
item_sub_1.export_itn = 0.0
item_sub_1.export_name = 'Plaster board'
item_sub_1.export_odt = 'SpectralAverage'
item_sub_1.export_rho = 1602.0
item_sub_1.export_rough = 'Smooth'
item_sub_1.export_sab = 0.4000000059604645
item_sub_1.export_sdiff = False
item_sub_1.export_sds = '0'
item_sub_1.export_shc = 836.0
item_sub_1.export_stn = 0.8999999761581421
item_sub_1.export_tab = 0.4000000059604645
item_sub_1.export_tc = 0.7264000177383423
item_sub_1.export_tctc = 0.0
item_sub_1.export_tempsemps = ''
item_sub_1.export_thi = 20.0
item_sub_1.export_vab = 0.4000000059604645
item_sub_1.export_vtn = 0.8999999761581421
item_sub_1.export_wgas = 'Air'
item_sub_1.name = ''
d.material_uv = 'N/A'
d.n_layers = 3
d.shad_att = False
d.thermalmass = False
