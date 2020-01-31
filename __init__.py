bl_info = {
    "name"     : "PBR Textures Bakery",
    "author"   : "kurotori",
    "version"  : (1,0,0),
    "blender"  : (2,80,0),
    "location" : "Properties > Material > PBR Textrues Bakery",
    "warning"  : "",
    "wiki_url" : "",
    "category" : "Material",
}

import bpy
import numpy as np

# 翻訳辞書
translation_dict = {
    "ja_JP": {
        ("*", "Active Object is"):
            "選択されたオブジェクト",
        ("*", "File Name"):
            "ファイル名",
        ("*", "Output(Optional)"):
            "出力先フォルダ（オプション）",
        ("*", "Normal map"):
            "ノーマルマップ",
        ("*", "Metallic map"):
            "メタリックマップ",
        ("*", "Roughness map"):
            "ラフネスマップ",
        ("*", "Bakeing objects are not select"):
            "ベイクするオブジェクトが選択されていません",
        ("*", "Material Output is not found"):
            "マテリアル出力ノードがありません",
        ("*", "Material Output Nodes input is not connected"):
            "マテリアル出力ノードのサーフェイス入力に何も接続されていません",
        ("*", "Material has incorrect Shader node"):
            "不正なシェーダーノードが接続されています",
        ("*", "Principled BSDF Node is not found"):
            "プリンシプルBSDFノードが見つかりません",
        ("*", "Baked Texture Type"):
            "ベイクするテクスチャの種類",
        ("*", "Create Textures"):
            "テクスチャを生成",
        ("*", "Combine Parameter Map"):
            "パラメーターマップとして結合",
        ("*","Enable combine map export"):
            "結合マップの出力を有効にする",
        ("*","CombineMap Suffix"):
            "結合マップの接尾辞",
        ("*","Active Object is: "):
            "有効なオブジェクト: "
    }
}

mapTypesSuffix = {
    'Base Color' : '_col',
    'Metallic' : '_met',
    'Roughness' : '_rgh',
    'Normal' : '_nrm'
    }

def saveTexture(context, image, format, name, dir):
    ext = ""
    if format == 'PNG':
        ext = ".png"
    else:
        ext = ".jpg"
    
    filepath_raw = dir + name + ext
    image.filepath_raw = filepath_raw
    image.file_format = format
    image.save()

class BakePanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "PBR Textures Bakery"
    bl_idname = "OBJECT_PT_PBRBAKE"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    def draw(self, context):
        layout = self.layout
        
        obj = context.object
        row = layout.row()
        row.label(text=bpy.app.translations.pgettext_iface("Active Object is: ") + obj.name)

        row = layout.row()
        row.prop(context.scene, "bakery_filename")

        row = layout.row()
        row.prop(context.scene, "bakery_out_directory")

        row = layout.row()
        row.prop(context.scene, "bakery_resolution")

        layout.separator()
        layout.label(text="Baked Texture Type")
        row = layout.row()
        column = layout.column(align=False)
        column.prop(context.scene, "bakery_bake_col")
        column.prop(context.scene, "bakery_bake_nrm")
        column.prop(context.scene, "bakery_bake_met")
        column.prop(context.scene, "bakery_bake_rgh")

        layout.separator()
        layout.label(text= bpy.app.translations.pgettext_iface("Combine Parameter Map"))
        row = layout.row()
        row.prop(context.scene, "bakery_bake_combine")

        if context.scene.bakery_bake_combine:
            row = layout.row()
            row.prop(context.scene, "bakery_combine_suffix")
            row = layout.row()
            column = layout.row()
            column = layout.column(align=True)
            column.prop(context.scene, "bakery_custom_tex_r")
            column.prop(context.scene, "bakery_custom_tex_g")
            column.prop(context.scene, "bakery_custom_tex_b")
            column.prop(context.scene, "bakery_custom_tex_a")

        row = layout.row()
        row.prop(context.scene, "bakery_margin")

        row = layout.row()
        row.operator("material.pbr_create_texture", 
            text = bpy.app.translations.pgettext_iface("Create Textures"),
            icon = "TEXTURE")

class PBR_CreateTextrue(bpy.types.Operator):
    bl_idname = 'material.pbr_create_texture'
    bl_label = "Create Textures"
    bl_description = "Create PBR textures"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        ob = context.active_object
        mat = ob.data.materials
        return (ob and ob.type == 'MESH' and len(mat) > 0)
    
    def draw(self, context):
        layout = self.layout
        
        terminate(global_undo)
        
        return {'FINISHED'}
    
    def execute(self, context):
        ao = context.active_object

        if not ao.select:
            self.report({'ERROR'}, 'Bakeing objects are not select')
            return {'FINISHED'}

        # マテリアルが正しいかどうかチェック
        for mat in ao.data.materials:
            if not self.CheckMaterial(mat):
                return {'FINISHED'}

        # レンダリングモードをCYCLESに変更し、サンプリング数を1にする
        default_render_mode = context.scene.render.engine
        context.scene.render.engine = 'CYCLES'
        default_samples = context.scene.cycles.samples
        context.scene.cycles.samples = 1

        rgh = None
        met = None

        if context.scene.bakery_bake_col:
            col = self.BakeTextureMultiMat(context.scene.bakery_filename, ao, 'Base Color', context.scene.bakery_resolution, context.scene.bakery_margin)
            if col is None:
                return{'FINISHED'}
            saveTexture(context, col, 'PNG', col.name, context.scene.bakery_out_directory)

        if context.scene.bakery_bake_met or context.scene.bakery_bake_combine:
            met = self.BakeTextureMultiMat(context.scene.bakery_filename, ao, 'Metallic', context.scene.bakery_resolution, context.scene.bakery_margin)
            if met is None:
                return{'FINISHED'}
            saveTexture(context, met, 'PNG', met.name, context.scene.bakery_out_directory)

        if context.scene.bakery_bake_nrm:
            nrm = self.BakeNormalMultiMat(context.scene.bakery_filename, ao, context.scene.bakery_resolution, context.scene.bakery_margin)
            if nrm is None:
                return{'FINISHED'}
            saveTexture(context, nrm, 'PNG', nrm.name, context.scene.bakery_out_directory)

        if context.scene.bakery_bake_rgh or context.scene.bakery_bake_combine:
            rgh = self.BakeTextureMultiMat(context.scene.bakery_filename, ao, 'Roughness', context.scene.bakery_resolution, context.scene.bakery_margin)
            if rgh is None:
                return{'FINISHED'}
            saveTexture(context, rgh, 'PNG', rgh.name, context.scene.bakery_out_directory)

        if context.scene.bakery_bake_combine:
            cmb = self.CreateCombineMap(context, context.scene.bakery_resolution,rgh, met, context.scene.bakery_combine_suffix)
            if cmb is None:
                return{'FINISHED'}
            saveTexture(context, cmb, 'PNG', cmb.name, context.scene.bakery_out_directory)

        # レンダリング設定を元に戻す
        context.scene.cycles.samples = default_samples
        context.scene.render.engine = default_render_mode

        return{'FINISHED'}

    # 正しいPBRマテリアルかどうかチェック
    def CheckMaterial(self, material):
        nodes = material.node_tree.nodes
        # マテリアルアウトプットが存在するかどうか
        if nodes.find('Material Output') == -1:
            self.report({'ERROR'}, 'Material Output is not found')
            return False
        
        matOutput = nodes['Material Output']

        result = True

        if not matOutput.inputs['Surface'].links:
            self.report({'ERROR'}, 'Material Output Nodes input is not connected')
            return False;

        for node in matOutput.inputs['Surface'].links:
            if node.from_node.type == 'MIX_SHADER':
                result = self.CheckNextMixNode(node.from_node)
            elif node.from_node.type == 'BSDF_PRINCIPLED':
                result = True and result
            else:
                result = False and result
        
        if not result:
            self.report({'ERROR'}, 'Material has incorrect Shader node')
            return False

        return True

    def CheckNextMixNode(self, mixnode):
        result = True
        for node in mixnode.inputs[1].links:
            if node.from_node.type == 'MIX_SHADER':
                result = self.CheckNextMixNode(node.from_node)
            elif node.from_node.type == 'BSDF_PRINCIPLED':
                result = True and result
            else:
                result = False and result
        
        for node in mixnode.inputs[2].links:
            if node.from_node.type == 'MIX_SHADER':
                result = self.CheckNextMixNode(node.from_node)
            elif node.from_node.type == 'BSDF_PRINCIPLED':
                result = True and result
            else:
                result = False and result
        
        return result

    def MakeBlImage(self, width, height, imgname):
        # 同名の画像が存在し、かつ同サイズだった場合はそれを使いまわし、サイズが異なれば新たに作成し直す
        if imgname in bpy.data.images and bpy.data.images[imgname].size[:] != (width, height):
            older = bpy.data.images[imgname]
            older.user_clear()
            bpy.data.images.remove( older )
        
        if imgname not in bpy.data.images:
            img = bpy.data.images.new(imgname, width, height, alpha=True)
            img.generated_color = (0,0,0,0)

        img = bpy.data.images[imgname]
        return img

    def BakeNormalMultiMat(self, filename, activeObject, resolution, margin):
        #img = bpy.data.images.new(filename + mapTypesSuffix['Normal'], width = resolution, height = resolution)
        img = self.MakeBlImage(resolution, resolution, filename + mapTypesSuffix['Normal'])

        NodeUVMapList = []
        NodeTextureList = []

        for mat in activeObject.data.materials:
            nodes = mat.node_tree.nodes
            node_uv_map = nodes.new(type = 'ShaderNodeUVMap')
            node_uv_map.uv_map = activeObject.data.uv_layers[0].name
            texNode = nodes.new(type='ShaderNodeTexImage')
            texNode.image = img
            nodes.active = texNode

            NodeUVMapList.append(node_uv_map)
            NodeTextureList.append(texNode)
        
        bpy.ops.object.bake(type='NORMAL', margin = margin, normal_space='TANGENT')

        for i, mat in enumerate(activeObject.data.materials):
            nodes = mat.node_tree.nodes
            nodes.remove(NodeUVMapList[i])
            nodes.remove(NodeTextureList[i])

        self.report({'INFO'}, img.name + " : Bake Complete!")
        return img

    def BakeTextureMultiMat(self, filename, activeObject, mapType, resolution, margin):
        mat = activeObject.data.materials[0]

        renderNodesList = []
        BSDFInConnectsList = []
        BSDFOutConnectsList = []
        NodeUVMapList = []
        NodeTextureList = []

         # ベイク
        #img = bpy.data.images.new(filename + mapTypesSuffix[mapType], width = resolution, height = resolution)
        img = self.MakeBlImage(resolution, resolution, filename + mapTypesSuffix[mapType])

        if mapType != 'Base Color':
            img.colorspace_settings.name = 'Non-Color' # Base Color 以外はNon-Colorに指定

        for mat in activeObject.data.materials:
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            matOutput = nodes['Material Output']

            # Material Output に接続されたノードを取得する
            # リストといいつつ大体１つしか見つからない。
            matOutputNodeList = []

            for node in matOutput.inputs['Surface'].links:
                matOutputNodeList.append({'From_Node' : node.from_node, 'From_Socket' : node.from_socket})
        
            renderNodes = [] # {Emis , BSDF}

            # プリンシプルBSDFのリスト
            pBSDFs = []

            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    renderNodes.append({ 'Emis' : nodes.new(type ='ShaderNodeEmission'), 'BSDF' : node})
                    pBSDFs.append(node)

            if len(pBSDFs) == 0:
                self.report({'ERROR'}, 'Principled BSDF Node is not found')
                return None

            # リンク切断
            BSDFInConnects = [] # [プリンシプルBSDFノード, BSDFの任意のソケット, BSDFの任意の入力に接続するノード, BSDFの任意の入力に接続するノードのソケット]
            BSDFOutConnects = [] # [BSDFの出力に接続するソケット、BSDF]
            for bsdf in pBSDFs:
                if bsdf.outputs['BSDF'].is_linked:
                    for node in bsdf.outputs['BSDF'].links:
                        BSDFOutConnects.append({'To_Socket' : node.to_socket, 'BSDF' : bsdf})
                else:
                    BSDFOutConnects.append({'To_Socket' : None , 'BSDF' : bsdf})

                if bsdf.inputs[mapType].is_linked:
                    for node in bsdf.inputs[mapType].links:
                        BSDFInConnects.append({ 'BSDF' : bsdf, 'BSDF_Input' : bsdf.inputs[mapType], 'From_Node' : node.from_node, 'From_Socket' : node.from_socket})
                        links.remove(node)
                else:
                    BSDFInConnects.append({'BSDF' : bsdf, 'BSDF_Input' : bsdf.inputs[mapType], 'From_Node' : None, 'From_Socket' : None})
        
            # エミッシブノードにリンク結合
            for i , bsdfIn in enumerate(BSDFInConnects):
                if bsdfIn['From_Socket'] is None:
                    if mapType == 'Metallic' or mapType == 'Roughness':
                        renderNodes[i]['Emis'].inputs['Strength'].default_value = BSDFOutConnects[i]['BSDF'].inputs[mapType].default_value
                    elif mapType == 'Base Color':
                        renderNodes[i]['Emis'].inputs['Color'].default_value = BSDFOutConnects[i]['BSDF'].inputs[mapType].default_value
                    else:
                        renderNodes[i]['Emis'].inputs['Color'].default_value = [0.5, 0.5, 1.0]
                    if not BSDFOutConnects[i]['To_Socket'] is None:
                        links.new(renderNodes[i]['Emis'].outputs['Emission'], BSDFOutConnects[i]['To_Socket'])
                else:
                    links.new(renderNodes[i]['Emis'].inputs['Color']    , bsdfIn['From_Socket']) #エミッシブノードの入力
                    if not BSDFOutConnects[i]['To_Socket'] is None:
                        links.new(renderNodes[i]['Emis'].outputs['Emission'], BSDFOutConnects[i]['To_Socket'])
            
            renderNodesList.append(renderNodes)
            BSDFInConnectsList.append(BSDFInConnects)
            BSDFOutConnectsList.append(BSDFOutConnects)
       
            node_uv_map = nodes.new(type = 'ShaderNodeUVMap')
            node_uv_map.uv_map = activeObject.data.uv_layers[0].name
            texNode = nodes.new(type='ShaderNodeTexImage')
            texNode.image = img
            nodes.active = texNode

            NodeUVMapList.append(node_uv_map)
            NodeTextureList.append(texNode)

        bpy.ops.object.bake(type='EMIT', margin = margin)

        for index, mat in enumerate(activeObject.data.materials):
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links

            nodes.remove(NodeUVMapList[index])
            nodes.remove(NodeTextureList[index])

            # 再リンク
            for i , bsdfOut in enumerate(BSDFOutConnectsList[index]):
                if not bsdfOut['To_Socket'] is None:
                    links.new(bsdfOut['To_Socket'], bsdfOut['BSDF'].outputs['BSDF'])
            
            for i , renderNode in enumerate(renderNodesList[index]):
                nodes.remove(renderNode['Emis'])
            
            for bsdfIn in BSDFInConnectsList[index]:
                if not bsdfIn['From_Socket'] is None:
                    links.new(bsdfIn['BSDF_Input'], bsdfIn['From_Socket'])
        
        self.report({'INFO'}, img.name + " : Bake Complete!")
        return img

    def CreateCombineMap(self, context, resolution, rgh, met, suffix):
        img = self.MakeBlImage(resolution, resolution, context.scene.bakery_filename + "_" + suffix)

        num_img = np.array(img.pixels[:])
        num_rgh = np.array(rgh.pixels[:])
        num_met = np.array(met.pixels[:])

        channels = [
            context.scene.bakery_custom_tex_r,
            context.scene.bakery_custom_tex_g,
            context.scene.bakery_custom_tex_b,
            context.scene.bakery_custom_tex_a,
        ]

        i = 0
        for channel in channels:
            if channel == 'max':
                num_img[i::4] = 1.0
            elif channel == 'min':
                num_img[i::4] = 0.0
            elif channel == 'mid':
                num_img[i::4] = 0.5
            elif channel == 'rgh':
                num_img[i::4] = num_rgh[0::4]
            elif channel == 'smt':
                num_img[i::4] = 1.0 - num_rgh[0::4]
            elif channel == 'met':
                num_img[i::4] = num_met[0::4]
            i+=1
        
        img.pixels = num_img

        return img

def register():
    
    bpy.utils.register_class(PBR_CreateTextrue)
    bpy.utils.register_class(BakePanel)
    bpy.types.Scene.bakery_resolution = bpy.props.IntProperty(
        name="Resolution",
        description="resolution",
        default=1024,
        min=32,
        max=8192
        )
    bpy.types.Scene.bakery_margin = bpy.props.IntProperty(
        name = "Margin",
        description = "margin",
        default=16,
        min=0,
        max= 32
        )
    bpy.types.Scene.bakery_filename = bpy.props.StringProperty(
        name="File Name",
        description="file name",
        default="tex"
        )
    bpy.types.Scene.bakery_out_directory = bpy.props.StringProperty(
        name="Output(Optional)",
        description="Output Drectory for created map",
        subtype="DIR_PATH"
        )

    bpy.types.Scene.bakery_bake_col = bpy.props.BoolProperty(
        name="Base Color",
        description = "Bake base color",
        default = True
        )

    bpy.types.Scene.bakery_bake_nrm = bpy.props.BoolProperty(
        name="Normal map",
        description = "Bake normal map",
        default = True
        )
    
    bpy.types.Scene.bakery_bake_met = bpy.props.BoolProperty(
        name="Metallic map",
        description = "Bake metallic map",
        default = True
        )
    
    bpy.types.Scene.bakery_bake_rgh = bpy.props.BoolProperty(
        name="Roughness map",
        description = "Bake Roughness map",
        default = True
        )
    
    bpy.types.Scene.bakery_bake_combine = bpy.props.BoolProperty(
        name="Enable combine map export",
        description = "Enable combine map export",
        default = False
        )

    bpy.types.Scene.bakery_custom_tex_r = bpy.props.EnumProperty(
        name = "R",
        description = "R",
        items = [
            ('rgh','Roughness','Roughness'),
            ('smt','Smoothness','Smoothness'),
            ('met','Metallic','Metallic'),
            ('max','Max_1','Max_1'),
            ('min','Min_0','Min_0'),
            ('mid','Mid_0.5','Mid_0.5')
        ],
        default = 'rgh'
    )
    
    bpy.types.Scene.bakery_custom_tex_g = bpy.props.EnumProperty(
        name = "G",
        description = "G",
        items = [
            ('rgh','Roughness','Roughness'),
            ('smt','Smoothness','Smoothness'),
            ('met','Metallic','Metallic'),
            ('max','Max_1','Max_1'),
            ('min','Min_0','Min_0'),
            ('mid','Mid_0.5','Mid_0.5')
        ],
        default = 'rgh'
    )

    bpy.types.Scene.bakery_custom_tex_b = bpy.props.EnumProperty(
        name = "B",
        description = "B",
        items = [
            ('rgh','Roughness','Roughness'),
            ('smt','Smoothness','Smoothness'),
            ('met','Metallic','Metallic'),
            ('max','Max_1','Max_1'),
            ('min','Min_0','Min_0'),
            ('mid','Mid_0.5','Mid_0.5')
        ],
        default = 'rgh'
    )

    bpy.types.Scene.bakery_custom_tex_a = bpy.props.EnumProperty(
        name = "A",
        description = "A",
        items = [
            ('rgh','Roughness','Roughness'),
            ('smt','Smoothness','Smoothness'),
            ('met','Metallic','Metallic'),
            ('max','Max_1','Max_1'),
            ('min','Min_0','Min_0'),
            ('mid','Mid_0.5','Mid_0.5')
        ],
        default = 'max'
    )

    bpy.types.Scene.bakery_combine_suffix = bpy.props.StringProperty(
        name="CombineMap Suffix",
        description="Combine map suffix",
        default="cmb"
    )
    
    bpy.app.translations.register(__name__, translation_dict)   # 辞書の登録

def unregister():
    bpy.app.translations.unregister(__name__)   # 辞書の削除
    bpy.utils.unregister_class(PBR_CreateTextrue)
    bpy.utils.unregister_class(BakePanel)

    del bpy.types.Scene.bakery_resolution
    del bpy.types.Scene.bakery_filename
    del bpy.types.Scene.bakery_out_directory

    del bpy.types.Scene.bakery_bake_col
    del bpy.types.Scene.bakery_bake_nrm
    del bpy.types.Scene.bakery_bake_met
    del bpy.types.Scene.bakery_bake_rgh

    del bpy.types.Scene.bakery_bake_combine
    del bpy.types.Scene.bakery_custom_tex_r
    del bpy.types.Scene.bakery_custom_tex_g
    del bpy.types.Scene.bakery_custom_tex_b
    del bpy.types.Scene.bakery_custom_tex_a
    del bpy.types.Scene.bakery_combine_suffix
    
if __name__ == "__main__":
    register()