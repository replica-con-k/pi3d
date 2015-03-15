from __future__ import absolute_import, division, print_function, unicode_literals

import ctypes, itertools
import numpy as np

from ctypes import c_float, c_int, c_short

from pi3d.constants import *
from pi3d.util import Log
from pi3d.util import Utility
from pi3d.util.Loadable import Loadable
from pi3d.util.Ctypes import c_floats, c_shorts

LOGGER = Log.logger(__name__)

class Buffer(Loadable):
  """Holds the vertex, normals, incices and tex_coords for each part of
  a Shape that needs to be rendered with a different material or texture
  Shape holds an array of Buffer objects.

  """
  def __init__(self, shape, pts, texcoords, faces, normals=None, smooth=True):
    """Generate a vertex buffer to hold data and indices. If no normals
    are provided then these are generated.

    Arguments:
      *shape*
        Shape object that this Buffer is a child of
      *pts*
        array of vertices tuples i.e. [(x0,y0,z0), (x1,y1,z1),...]
      *texcoords*
        array of texture (uv) coordinates tuples
        i.e. [(u0,v0), (u1,v1),...]
      *faces*
        array of indices (of pts array) defining triangles
        i.e. [(a0,b0,c0), (a1,b1,c1),...]

    Keyword arguments:
      *normals*
        array of vector component tuples defining normals at each
        vertex i.e. [(x0,y0,z0), (x1,y1,z1),...]
      *smooth*
        if calculating normals then average normals for all faces
        meeting at this vertex, otherwise just use first (for speed).

    """
    super(Buffer, self).__init__()

    # Uniform variables all in one array!
    self.unib = (c_float * 12)(0.0, 0.0, 0.0,
                              0.5, 0.5, 0.5,
                              1.0, 1.0, 0.0,
                              0.0, 0.0, 0.0)
    """ pass to shader array of vec3 uniform variables:

    ===== ============================ ==== ==
    vec3        description            python
    ----- ---------------------------- -------
    index                              from to
    ===== ============================ ==== ==
        0  ntile, shiny, blend           0   2
        1  material                      3   5
        2  umult, vmult, point_size      6   8
        3  u_off, v_off, line_width      9  10
    ===== ============================ ==== ==
    """
    #self.shape = shape
    self.textures = []
    self.vertices = np.array(pts, dtype="float32")
    self.tex_coords = np.array(texcoords, dtype="float32")
    self.indices = np.array(faces, dtype="short")

    if normals == None: #i.e. normals will only be generated if explictly None
      LOGGER.debug('Calculating normals ...')
      self.normals = self.calc_normals()
    else:
      self.normals = np.array(normals, dtype="float32")
      
    self.material = (0.5, 0.5, 0.5, 1.0)
    self.draw_method = GL_TRIANGLES
    self._pack_array_buffer()
    self._pack_element_array_buffer()

  def calc_normals(self):
    normals = np.zeros(self.vertices.shape, dtype="float32") #empty array rights size
    fv = self.vertices[self.indices] #expand faces with x,y,z values for each vertex
    #cross product of two edges of triangles
    fn = np.cross(fv[:,1] - fv[:,0], fv[:,2] - fv[:,0])
    fn = Utility.normalize_v3(fn)
    normals[self.indices[:,0]] += fn #add up all normal vectors for a vertex
    normals[self.indices[:,1]] += fn
    normals[self.indices[:,2]] += fn
    return Utility.normalize_v3(normals)

  def _pack_array_buffer(self):
    # Pack points,normals and texcoords into tuples and convert to ctype floats.
    n_verts = len(self.vertices)
    if len(self.tex_coords) != n_verts:
      if len(self.normals) != n_verts:
        self.N_BYTES = 12 # only use pts
        self.array_buffer = self.vertices
      else:
        self.N_BYTES = 24 # use pts and normals
        self.array_buffer = np.concatenate((self.vertices, self.normals),
                            axis=1)
    else:
      self.N_BYTES = 32 # use all three NB doesn't check that normals are there
      self.array_buffer = np.concatenate((self.vertices, self.normals, self.tex_coords),
                          axis=1)

  def _pack_element_array_buffer(self):
    self.ntris = len(self.indices)
    self.element_array_buffer = self.indices
    from pi3d.Display import Display
    self.disp = Display.INSTANCE # rely on there always being one!

  def __del__(self):
    #super(Buffer, self).__del__() #TODO supposed to always call super.__del__
    if not self.opengl_loaded:
      return True
    self.disp.vbufs_dict[str(self.vbuf)][1] = 1
    self.disp.ebufs_dict[str(self.ebuf)][1] = 1
    self.disp.tidy_needed = True

  def re_init(self, pts=None, texcoords=None, normals=None, offset=0):
    """Only reset the opengl buffer variables: vertices, tex_coords, normals
    (which will not be generated if not supplied)
    **NB this method will go horribly wrong if you change the size of the
    arrays supplied in the argument as the opengles buffers are reused
    At least one of pts, texcoords or normals must be a list**

      Arguments:
        *pts*
          list of (x,y,z) tuples, default None
        *texcoords*
          list of (u,v) tuples, default None
        *normals*
          list of (x,y,z) tuples, default None
        *offset*
          number of vertices offset from the start of vertices, default 0
      """
    stride = int(self.N_BYTES / 4) #i.e. 3, 6 or 8 This can't change from init
    if not (pts == None):
      n = len(pts)
      if not (isinstance(pts, np.ndarray)):
        pts = np.array(pts)
      #self.array_buffer[offset:(offset + n), 0:3] = self.vertices[offset:(offset + n),:] = pts[:,:]
      self.array_buffer[offset:(offset + n), 0:3] = pts[:,:]
    if not (normals == None): 
      n = len(normals)
      if not (isinstance(normals, np.ndarray)):
        normals = np.array(normals)
      #self.array_buffer[offset:(offset + n), 3:6] = self.normals[offset:(offset + n),:] = normals[:,:]
      self.array_buffer[offset:(offset + n), 3:6] = normals[:,:]
    if not (texcoords == None):
      n = len(texcoords)
      if not (isinstance(texcoords, np.ndarray)):
        texcoords = np.array(texcoords)
      #self.array_buffer[offset:(offset + n), 6:8] = self.tex_coords[offset:(offset + n),:] = texcoords[:,:]
      self.array_buffer[offset:(offset + n), 6:8] = texcoords[:,:]
    self._select()
    opengles.glBufferSubData(GL_ARRAY_BUFFER, 0,
                      self.array_buffer.nbytes,
                      self.array_buffer.ctypes.data)

  def _load_opengl(self):
    self.vbuf = c_int()
    opengles.glGenBuffers(1, ctypes.byref(self.vbuf))
    self.ebuf = c_int()
    opengles.glGenBuffers(1, ctypes.byref(self.ebuf))
    self.disp.vbufs_dict[str(self.vbuf)] = [self.vbuf, 0]
    self.disp.ebufs_dict[str(self.ebuf)] = [self.ebuf, 0]
    self._select()
    opengles.glBufferData(GL_ARRAY_BUFFER,
                          self.array_buffer.nbytes,
                          self.array_buffer.ctypes.data,
                          GL_STATIC_DRAW)
    opengles.glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                          self.element_array_buffer.nbytes,
                          self.element_array_buffer.ctypes.data,
                          GL_STATIC_DRAW)

  def _unload_opengl(self):
    opengles.glDeleteBuffers(1, ctypes.byref(self.vbuf))
    opengles.glDeleteBuffers(1, ctypes.byref(self.ebuf))

  def _select(self):
    """Makes our buffers active."""
    opengles.glBindBuffer(GL_ARRAY_BUFFER, self.vbuf)
    opengles.glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebuf)

  def set_draw_details(self, shader, textures, ntiles=0.0, shiny=0.0,
                       umult=1.0, vmult=1.0):
    """Can be used to set information needed for drawing as a one off
    rather than sending as arguments to draw().

    Arguments:
      *shader*
        Shader object
      *textures*
        array of Texture objects

    Keyword arguments:
      *ntiles*
        multiple for tiling normal map which can be less than or greater
        than 1.0. 0.0 disables the normal mapping, float
      *shiny*
        how strong to make the reflection 0.0 to 1.0, float
      *umult*
        multiplier for tiling the texture in the u direction
      *vmult*
        multiplier for tiling the texture in the v direction
    """
    self.shader = shader
    self.textures = textures # array of Textures
    self.unib[0] = ntiles
    self.unib[1] = shiny
    self.unib[6] = umult
    self.unib[7] = vmult

  def set_material(self, mtrl):
    self.unib[3:6] = mtrl[0:3]

  def set_textures(self, textures):
    self.textures = textures

  def set_offset(self, offset=(0.0, 0.0)):
    self.unib[9:11] = offset

  def draw(self, shape=None, shader=None, textures=None, ntl=None, shny=None, fullset=True):
    """Draw this Buffer, called by the parent Shape.draw()

    Keyword arguments:
      *shape*
        Shape object this Buffer belongs to, has to be passed at draw to avoid
        circular reference
      *shader*
        Shader object
      *textures*
        array of Texture objects
      *ntl*
        multiple for tiling normal map which can be less than or greater
        than 1.0. 0.0 disables the normal mapping, float
      *shiny*
        how strong to make the reflection 0.0 to 1.0, float
    """
    self.load_opengl()

    shader = shader or self.shader
    textures = textures or self.textures
    if ntl:
      self.unib[0] = ntl
    if shny:
      self.unib[1] = shny
    self._select()

    opengles.glVertexAttribPointer(shader.attr_vertex, 3, GL_FLOAT, 0, self.N_BYTES, 0)
    opengles.glEnableVertexAttribArray(shader.attr_vertex)
    if self.N_BYTES > 12:
      opengles.glVertexAttribPointer(shader.attr_normal, 3, GL_FLOAT, 0, self.N_BYTES, 12)
      opengles.glEnableVertexAttribArray(shader.attr_normal)
      if self.N_BYTES > 24:
        opengles.glVertexAttribPointer(shader.attr_texcoord, 2, GL_FLOAT, 0, self.N_BYTES, 24)
        opengles.glEnableVertexAttribArray(shader.attr_texcoord)

    opengles.glDisable(GL_BLEND)

    self.unib[2] = 0.6
    for t, texture in enumerate(textures):
      if (self.disp.last_textures[t] != texture or
            self.disp.last_shader != shader): # very slight speed increase for sprites
        opengles.glActiveTexture(GL_TEXTURE0 + t)
        assert texture.tex(), 'There was an empty texture in your Buffer.'
        opengles.glBindTexture(GL_TEXTURE_2D, texture.tex())
        opengles.glUniform1i(shader.unif_tex[t], t)
        self.disp.last_textures[t] = texture

      if texture.blend:
        # i.e. if any of the textures set to blend then all will for this shader.
        self.unib[2] = 0.05

    if self.unib[2] != 0.6 or shape.unif[17] < 1.0 or shape.unif[16] < 1.0:
      #use unib[2] as flag to indicate if any Textures to be blended
      #needs to be done outside for..textures so materials can be transparent
        opengles.glEnable(GL_BLEND)
        self.unib[2] = 0.05

    self.disp.last_shader = shader

    opengles.glUniform3fv(shader.unif_unib, 4, ctypes.byref(self.unib))

    opengles.glEnable(GL_DEPTH_TEST) # TODO find somewhere more efficient to do this

    opengles.glDrawElements(self.draw_method, self.ntris * 3, GL_UNSIGNED_SHORT, 0)

  # Implement pickle/unpickle support
  def __getstate__(self):
    return {
      'unib': list(self.unib),
      'array_buffer': self.array_buffer,
      'element_array_buffer': self.element_array_buffer,
      'material': self.material,
      'textures': self.textures,
      'draw_method': self.draw_method,
      'ntris': self.ntris,
      'N_BYTES': self.N_BYTES
      }
  
  def __setstate__(self, state):
    unib_tuple = tuple(state['unib'])
    self.unib = (ctypes.c_float * 12)(*unib_tuple)
    self.array_buffer = state['array_buffer']
    self.element_array_buffer = state['element_array_buffer']
    self.material = state['material']
    self.textures = state['textures']
    self.draw_method = state['draw_method']
    self.opengl_loaded = False
    self.disk_loaded = True
    self.ntris = state['ntris']
    self.N_BYTES = state['N_BYTES']
    from pi3d.Display import Display
    self.disp = Display.INSTANCE # rely on there always being one!
