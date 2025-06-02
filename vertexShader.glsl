#version 330

in vec3 positionAttribute;
in vec3	normalAttribute;
in vec2	texCoordAttribute;

uniform mat4 modelToClipTransform;
uniform mat4 modelToViewTransform;
uniform mat3 modelToViewNormalTransform;

// Out variables decalred in a vertex shader can be accessed in the subsequent stages.
// For a pixel shader the variable is interpolated (the type of interpolation can be modified, try placing 'flat' in front, and also in the fragment shader!).
out VertexData
{
	vec3 v2f_viewSpaceNormal;
	vec3 v2f_viewSpacePosition;
	vec2 v2f_texCoord;
};

void main() 
{
	// gl_Position is a buit in out variable that gets passed on to the clipping and rasterization stages.
  // it must be written in order to produce any drawn geometry. 
  // We transform the position using one matrix multiply from model to clip space, note the added 1 at the end of the position.
	gl_Position = modelToClipTransform * vec4(positionAttribute, 1.0);
	// We transform the normal to view space using the normal transform (which is the inverse-transpose of the rotation part of the modelToViewTransform)
  // Just using the rotation is only valid if the matrix contains only rotation and uniform scaling.
	v2f_viewSpaceNormal = normalize(modelToViewNormalTransform * normalAttribute);
	v2f_viewSpacePosition = (modelToViewTransform * vec4(positionAttribute, 1.0)).xyz;
	// The texture coordinate is just passed through
	v2f_texCoord = texCoordAttribute;
}
