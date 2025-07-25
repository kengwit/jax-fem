import os
import gmsh
import numpy as onp
import meshio

from jax_fem.basis import get_elements
from jax_fem.basis import get_face_shape_vals_and_grads

import jax
import jax.numpy as np


class Mesh():
    """Mesh manager.

    Attributes
    ----------
    points : NumpyArray
        Shape is (num_total_nodes, dim).
    cells: NumpyArray
        Shape is (num_cells, num_nodes).
    """
    def __init__(self, points, cells, ele_type='TET4'):
        # TODO (Very important for debugging purpose!): Assert that cells must have correct orders
        self.points = points
        self.cells = cells
        self.ele_type = ele_type

    def count_selected_faces(self, location_fn):
        """Given location functions, compute the number of faces that satisfy the location function. 
        Useful for setting up distributed load conditions.

        Parameters
        ----------
        location_fns : list
            :attr:`~jax_fem.problem.Problem.location_fns`

        Returns
        -------
        face_count : int
        """
        _, _, _, _, face_inds = get_face_shape_vals_and_grads(self.ele_type)
        cell_points = onp.take(self.points, self.cells, axis=0)
        cell_face_points = onp.take(cell_points, face_inds, axis=1)

        vmap_location_fn = jax.vmap(location_fn)

        def on_boundary(cell_points):
            boundary_flag = vmap_location_fn(cell_points)
            return onp.all(boundary_flag)

        vvmap_on_boundary = jax.vmap(jax.vmap(on_boundary))
        boundary_flags = vvmap_on_boundary(cell_face_points)
        boundary_inds = onp.argwhere(boundary_flags)
        return boundary_inds.shape[0]


def check_mesh_TET4(points, cells):
    """Check the order of TET4 element.

    Parameters
    ----------
    points : list
        :attr:`~.Mesh.points`
    cells : list
        :attr:`~.Mesh.cells`

    Returns
    -------
    qlts : JaxArray
    """
    def quality(pts):
        p1, p2, p3, p4 = pts
        v1 = p2 - p1
        v2 = p3 - p1
        v12 = np.cross(v1, v2)
        v3 = p4 - p1
        return np.dot(v12, v3)
    qlts = jax.vmap(quality)(points[cells])
    return qlts


def get_meshio_cell_type(ele_type):
    """Convert element type into a compatible string with 
    `meshio <https://github.com/nschloe/meshio/blob/9dc6b0b05c9606cad73ef11b8b7785dd9b9ea325/src/meshio/xdmf/common.py#L36>`_.

    Parameters
    ----------
    ele_type : str
        :attr:`~jax_fem.fe.FiniteElement.ele_type`

    Returns
    -------
    cell_type : str
        Compatible with meshio.
    """
    if ele_type == 'TET4':
        cell_type = 'tetra'
    elif ele_type == 'TET10':
        cell_type = 'tetra10'
    elif ele_type == 'HEX8':
        cell_type = 'hexahedron'
    elif ele_type == 'HEX27':
        cell_type = 'hexahedron27'
    elif  ele_type == 'HEX20':
        cell_type = 'hexahedron20'
    elif ele_type == 'TRI3':
        cell_type = 'triangle'
    elif ele_type == 'TRI6':
        cell_type = 'triangle6'
    elif ele_type == 'QUAD4':
        cell_type = 'quad'
    elif ele_type == 'QUAD8':
        cell_type = 'quad8'
    else:
        raise NotImplementedError
    return cell_type


def rectangle_mesh(Nx, Ny, domain_x, domain_y):
    """Generate QUAD4 mesh.

    Parameters
    ----------
    Nx : int
        Number of nodes along x-axis.
    Ny : int
        Number of nodes along y-axis.
    domain_x : float
        Length of side along x-axis.
    domain_y : float
        Length of side along y-axis.
    """
    dim = 2
    x = onp.linspace(0, domain_x, Nx + 1)
    y = onp.linspace(0, domain_y, Ny + 1)
    xv, yv = onp.meshgrid(x, y, indexing='ij')
    points_xy = onp.stack((xv, yv), axis=dim)
    points = points_xy.reshape(-1, dim)
    points_inds = onp.arange(len(points))
    points_inds_xy = points_inds.reshape(Nx + 1, Ny + 1)
    inds1 = points_inds_xy[:-1, :-1]
    inds2 = points_inds_xy[1:, :-1]
    inds3 = points_inds_xy[1:, 1:]
    inds4 = points_inds_xy[:-1, 1:]
    cells = onp.stack((inds1, inds2, inds3, inds4), axis=dim).reshape(-1, 4)
    out_mesh = meshio.Mesh(points=points, cells={'quad': cells})
    return out_mesh


def box_mesh(Nx, Ny, Nz, domain_x, domain_y, domain_z):
    """Generate HEX8 mesh.

    Parameters
    ----------
    Nx : int
        Number of nodes along x-axis.
    Ny : int
        Number of nodes along y-axis.
    Nz : int
        Number of nodes along z-axis.
    domain_x : float
        Length of side along x-axis.
    domain_y : float
        Length of side along y-axis.
    domain_z : float
        Length of side along z-axis.
    """
    dim = 3
    x = onp.linspace(0, domain_x, Nx + 1)
    y = onp.linspace(0, domain_y, Ny + 1)
    z = onp.linspace(0, domain_z, Nz + 1)
    xv, yv, zv = onp.meshgrid(x, y, z, indexing='ij')
    points_xyz = onp.stack((xv, yv, zv), axis=dim)
    points = points_xyz.reshape(-1, dim)
    points_inds = onp.arange(len(points))
    points_inds_xyz = points_inds.reshape(Nx + 1, Ny + 1, Nz + 1)
    inds1 = points_inds_xyz[:-1, :-1, :-1]
    inds2 = points_inds_xyz[1:, :-1, :-1]
    inds3 = points_inds_xyz[1:, 1:, :-1]
    inds4 = points_inds_xyz[:-1, 1:, :-1]
    inds5 = points_inds_xyz[:-1, :-1, 1:]
    inds6 = points_inds_xyz[1:, :-1, 1:]
    inds7 = points_inds_xyz[1:, 1:, 1:]
    inds8 = points_inds_xyz[:-1, 1:, 1:]
    cells = onp.stack((inds1, inds2, inds3, inds4, inds5, inds6, inds7, inds8),
                      axis=dim).reshape(-1, 8)
    out_mesh = meshio.Mesh(points=points, cells={'hexahedron': cells})
    return out_mesh


def box_mesh_gmsh(Nx, Ny, Nz, domain_x, domain_y, domain_z, data_dir, ele_type='HEX8'):
    """Generate a box mesh with the help of `gmsh <https://gmsh.info/>`_.
    Some useful links include
    `tutorial_hex <https://gitlab.onelab.info/gmsh/gmsh/-/blob/master/examples/api/hex.py>`_, 
    `tutorial_t1 <https://gitlab.onelab.info/gmsh/gmsh/-/blob/gmsh_4_7_1/tutorial/python/t1.py>`_, 
    `tutorial_t3 <https://gitlab.onelab.info/gmsh/gmsh/-/blob/gmsh_4_7_1/tutorial/python/t3.py>`_.

    Parameters
    ----------
    Nx : int
        Number of nodes along x-axis.
    Ny : int
        Number of nodes along y-axis.
    Nz : int
        Number of nodes along z-axis.
    domain_x : float
        Length of side along x-axis.
    domain_y : float
        Length of side along y-axis.
    domain_z : float
        Length of side along z-axis.    
    data_dir : str
        A directory to store the generated mesh.
    ele_type : str
        The type is :attr:`~jax_fem.fe.FiniteElement.ele_type`.
        Accept 'HEX8', 'TET4' or 'TET10'.

    Returns
    -------
    out_mesh : MeshioMesh
        Mesh in meshio format.
    """

    assert ele_type != 'HEX20', f"gmsh cannot produce HEX20 mesh?"

    cell_type = get_meshio_cell_type(ele_type)
    _, _, _, _, degree, _ = get_elements(ele_type)

    msh_dir = os.path.join(data_dir, 'msh')
    os.makedirs(msh_dir, exist_ok=True)
    msh_file = os.path.join(msh_dir, 'box.msh')

    offset_x = 0.
    offset_y = 0.
    offset_z = 0.

    gmsh.initialize()
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)  # save in old MSH format
    if cell_type.startswith('tetra'):
        Rec2d = False  # tris or quads
        Rec3d = False  # tets, prisms or hexas
    else:
        Rec2d = True
        Rec3d = True
    p = gmsh.model.geo.addPoint(offset_x, offset_y, offset_z)
    l = gmsh.model.geo.extrude([(0, p)], domain_x, 0, 0, [Nx], [1])
    s = gmsh.model.geo.extrude([l[1]], 0, domain_y, 0, [Ny], [1], recombine=Rec2d)
    v = gmsh.model.geo.extrude([s[1]], 0, 0, domain_z, [Nz], [1], recombine=Rec3d)

    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(degree)
    gmsh.write(msh_file)
    gmsh.finalize()

    mesh = meshio.read(msh_file)
    points = mesh.points # (num_total_nodes, dim)
    cells =  mesh.cells_dict[cell_type] # (num_cells, num_nodes)
    out_mesh = meshio.Mesh(points=points, cells={cell_type: cells})

    return out_mesh


def cylinder_mesh_gmsh(data_dir, R=5, H=10, circle_mesh=5, hight_mesh=20, rect_ratio=0.4):
    """Generate a cylinder mesh with the help of `gmsh <https://gmsh.info/>`_.

    Contributed by Xinxin Wu at PKU in July, 2022, folloing the
    `tutorial <https://www.researchgate.net/post/How_can_I_create_a_structured_mesh_using_a_transfinite_volume_in_gmsh>`_.

    Parameters
    ----------
    data_dir : str
        A directory to store the generated mesh.
    R : float 
        radius
    H : float
        hight
    circle_mesh : int
        num of meshs in circle lines
    hight_mesh: int
        num of meshs in hight
    rect_ratio : float 
        rect length/R

    Returns
    -------
    out_mesh : MeshioMesh
        Mesh in meshio format.
    """
    rect_coor = R*rect_ratio
    msh_dir = os.path.join(data_dir, 'msh')
    os.makedirs(msh_dir, exist_ok=True)
    geo_file = os.path.join(msh_dir, 'cylinder.geo')
    msh_file = os.path.join(msh_dir, 'cylinder.msh')

    string='''
        Point(1) = {{0, 0, 0, 1.0}};
        Point(2) = {{-{rect_coor}, {rect_coor}, 0, 1.0}};
        Point(3) = {{{rect_coor}, {rect_coor}, 0, 1.0}};
        Point(4) = {{{rect_coor}, -{rect_coor}, 0, 1.0}};
        Point(5) = {{-{rect_coor}, -{rect_coor}, 0, 1.0}};
        Point(6) = {{{R}*Cos(3*Pi/4), {R}*Sin(3*Pi/4), 0, 1.0}};
        Point(7) = {{{R}*Cos(Pi/4), {R}*Sin(Pi/4), 0, 1.0}};
        Point(8) = {{{R}*Cos(-Pi/4), {R}*Sin(-Pi/4), 0, 1.0}};
        Point(9) = {{{R}*Cos(-3*Pi/4), {R}*Sin(-3*Pi/4), 0, 1.0}};

        Line(1) = {{2, 3}};
        Line(2) = {{3, 4}};
        Line(3) = {{4, 5}};
        Line(4) = {{5, 2}};
        Line(5) = {{2, 6}};
        Line(6) = {{3, 7}};
        Line(7) = {{4, 8}};
        Line(8) = {{5, 9}};

        Circle(9) = {{6, 1, 7}};
        Circle(10) = {{7, 1, 8}};
        Circle(11) = {{8, 1, 9}};
        Circle(12) = {{9, 1, 6}};

        Curve Loop(1) = {{1, 2, 3, 4}};
        Plane Surface(1) = {{1}};
        Curve Loop(2) = {{1, 6, -9, -5}};
        Plane Surface(2) = {{2}};
        Curve Loop(3) = {{2, 7, -10, -6}};
        Plane Surface(3) = {{3}};
        Curve Loop(4) = {{3, 8, -11, -7}};
        Plane Surface(4) = {{4}};
        Curve Loop(5) = {{4, 5, -12, -8}};
        Plane Surface(5) = {{5}};

        Transfinite Curve {{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}} = {circle_mesh} Using Progression 1;

        Transfinite Surface {{1}};
        Transfinite Surface {{2}};
        Transfinite Surface {{3}};
        Transfinite Surface {{4}};
        Transfinite Surface {{5}};
        Recombine Surface {{1, 2, 3, 4, 5}};

        Extrude {{0, 0, {H}}} {{
          Surface{{1:5}}; Layers {{{hight_mesh}}}; Recombine;
        }}

        Mesh 3;'''.format(R=R, H=H, rect_coor=rect_coor, circle_mesh=circle_mesh, hight_mesh=hight_mesh)

    with open(geo_file, "w") as f:
        f.write(string)
    os.system("gmsh -3 {geo_file} -o {msh_file} -format msh2".format(geo_file=geo_file, msh_file=msh_file))

    mesh = meshio.read(msh_file)
    points = mesh.points # (num_total_nodes, dim)
    cells =  mesh.cells_dict['hexahedron'] # (num_cells, num_nodes)

    # The mesh somehow has two redundant points...
    points = onp.vstack((points[1:14], points[15:]))
    cells = onp.where(cells > 14, cells - 2, cells - 1)

    out_mesh = meshio.Mesh(points=points, cells={'hexahedron': cells})
    return out_mesh
