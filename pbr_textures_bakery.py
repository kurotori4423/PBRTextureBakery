bl_info = {
    "name"     : "PBR Textures Bakery",
    "author"   : "kurotori",
    "version"  : (0,1,0),
    "blender"  : (2,80,0),
    "location" : "Properties > Material > PBR Textrues Bakery",
    "warning"  : "",
    "wiki_url" : "",
    "category" : "Material",
}

import bpy

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
        row.label(text="Active Object is: " + obj.name)

        row = layout.row()
        row.prop(context.scene, "bakery_filename")

        row = layout.row()
        row.prop(context.scene, "bakery_out_directory")

        row = layout.row()
        row.prop(context.scene, "bakery_resolution")

        row = layout.row()
        row.operator("material.pbr_create_texture")

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

        # マテリアルが正しいかどうかチェック
        for mat in ao.data.materials:
            if not self.CheckMaterial(mat):
                return {'FINISHED'}

        context.scene.render.engine = 'CYCLES'

        col = self.BakeTexture(context.scene.bakery_filename, ao, 'Base Color', context.scene.bakery_resolution)
        if col is None:
            return{'FINISHED'}
        saveTexture(context, col, 'PNG', col.name, context.scene.bakery_out_directory)

        met = self.BakeTexture(context.scene.bakery_filename, ao, 'Metallic', context.scene.bakery_resolution)
        if met is None:
            return{'FINISHED'}
        saveTexture(context, met, 'PNG', met.name, context.scene.bakery_out_directory)

        nrm = self.BakeNormal(context.scene.bakery_filename, ao, context.scene.bakery_resolution)
        if nrm is None:
            return{'FINISHED'}
        saveTexture(context, nrm, 'PNG', nrm.name, context.scene.bakery_out_directory)

        rgh = self.BakeTexture(context.scene.bakery_filename, ao, 'Roughness', context.scene.bakery_resolution)
        if rgh is None:
            return{'FINISHED'}
        saveTexture(context, rgh, 'PNG', rgh.name, context.scene.bakery_out_directory)

        return{'FINISHED'}
    
    def BakeNormal(self, filename, activeObject, resolution):
        mat = activeObject.data.materials[0]
        nodes = mat.node_tree.nodes

        if nodes.find('Material Output') == -1:
            self.report({'ERROR'}, 'Material Output is not found')
            return None
        
        img = bpy.data.images.new(filename + mapTypesSuffix['Normal'], width = resolution, height = resolution)
        node_uv_map = nodes.new(type = 'ShaderNodeUVMap')
        node_uv_map.uv_map = activeObject.data.uv_layers[0].name
        texNode = nodes.new(type='ShaderNodeTexImage')
        texNode.image = img
        nodes.active = texNode
        bpy.ops.object.bake(type='NORMAL', margin = 8, normal_space='TANGENT')

        nodes.remove(node_uv_map)
        nodes.remove(texNode)

        self.report({'INFO'}, img.name + " : Bake Complete!")
        return img

    # 正しいPBRマテリアルかどうかチェック
    def CheckMaterial(self, material):
        nodes = material.node_tree.nodes
        # マテリアルアウトプットが存在するかどうか
        if nodes.find('Material Output') == -1:
            self.report({'ERROR'}, 'Material Output is not found')
            return False
        
        matOutput = nodes['Material Output']

        result = True
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
            print(node.from_node.name)
            if node.from_node.type == 'MIX_SHADER':
                result = self.CheckNextMixNode(node.from_node)
            elif node.from_node.type == 'BSDF_PRINCIPLED':
                result = True and result
            else:
                result = False and result
                print("find")
        
        for node in mixnode.inputs[2].links:
            print(node.from_node.name)
            if node.from_node.type == 'MIX_SHADER':
                result = self.CheckNextMixNode(node.from_node)
            elif node.from_node.type == 'BSDF_PRINCIPLED':
                result = True and result
            else:
                result = False and result
                print("find")
        
        return result

    def BakeTexture(self, filename, activeObject, mapType, resolution):
        mat = activeObject.data.materials[0]
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        if nodes.find('Material Output') == -1:
            self.report({'ERROR'}, 'Material Output is not found')
            return None

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
        
        # ベイク
        img = bpy.data.images.new(filename + mapTypesSuffix[mapType], width = resolution, height = resolution)
        node_uv_map = nodes.new(type = 'ShaderNodeUVMap')
        node_uv_map.uv_map = activeObject.data.uv_layers[0].name
        texNode = nodes.new(type='ShaderNodeTexImage')
        texNode.image = img
        nodes.active = texNode
        bpy.ops.object.bake(type='EMIT', margin = 8)

        nodes.remove(node_uv_map)
        nodes.remove(texNode)

        # 再リンク
        for i , bsdfOut in enumerate(BSDFOutConnects):
            if not bsdfOut['To_Socket'] is None:
                links.new(bsdfOut['To_Socket'], bsdfOut['BSDF'].outputs['BSDF'])
        
        for i , renderNode in enumerate(renderNodes):
            nodes.remove(renderNode['Emis'])
        
        for bsdfIn in BSDFInConnects:
            if not bsdfIn['From_Socket'] is None:
                links.new(bsdfIn['BSDF_Input'], bsdfIn['From_Socket'])
        self.report({'INFO'}, img.name + " : Bake Complete!")
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


def unregister():
    bpy.utils.unregister_class(PBR_CreateTextrue)
    bpy.utils.unregister_class(BakePanel)

    del bpy.types.Scene.bakery_resolution
    del bpy.types.Scene.bakery_filename
    del bpy.types.Scene.bakery_out_directory
    
    
if __name__ == "__main__":
    register()