=====
Usage
=====

To use pypcd in a project::

    import pypcd

Reading and Writing PCD Files
-----------------------------

Reading PCD files is straightforward::

    # Read from a file path
    pc = pypcd.PointCloud.from_path('cloud.pcd')
    
    # Read from a file object
    with open('cloud.pcd', 'rb') as f:
        pc = pypcd.PointCloud.from_fileobj(f)
    
    # Read from a buffer
    with open('cloud.pcd', 'rb') as f:
        buf = f.read()
    pc = pypcd.PointCloud.from_buffer(buf)

Writing PCD files supports different formats::

    # Save in ASCII format
    pypcd.save_point_cloud(pc, 'cloud_ascii.pcd')
    
    # Save in binary format
    pypcd.save_point_cloud_bin(pc, 'cloud_binary.pcd')
    
    # Save in compressed binary format
    pypcd.save_point_cloud_bin_compressed(pc, 'cloud_binary_compressed.pcd')
    
    # Alternative method using the PointCloud object directly
    pc.save_pcd('cloud.pcd', compression='ascii')  # or 'binary' or 'binary_compressed'

Writing PLY Files
-----------------

The package also supports writing point clouds to PLY format::

    # Save in ASCII format (default)
    pypcd.save_point_cloud_ply(pc, 'cloud.ply')
    
    # Save in binary format
    pypcd.save_point_cloud_ply(pc, 'cloud.ply', data_format='binary')

Creating Point Clouds from Scratch
----------------------------------

There are several ways to create point clouds from scratch:

XYZ Point Cloud::

    import numpy as np
    
    # Create an Nx3 array of XYZ coordinates
    xyz = np.random.rand(100, 3)  # 100 random points
    
    # Create point cloud from XYZ data
    pc = pypcd.make_xyz_point_cloud(xyz)

XYZ Point Cloud with RGB Data::

    # Create an Nx4 array with XYZ and RGB data
    # RGB values should be encoded as a single float32
    xyz_rgb = np.zeros((100, 4), dtype=np.float32)
    xyz_rgb[:, :3] = np.random.rand(100, 3)  # XYZ coordinates
    
    # Encode RGB values (each component in range 0-255)
    r, g, b = 255, 128, 0  # Example RGB values
    rgb_float = struct.unpack('f', struct.pack('i', r << 16 | g << 8 | b))[0]
    xyz_rgb[:, 3] = rgb_float
    
    # Create point cloud
    pc = pypcd.make_xyz_rgb_point_cloud(xyz_rgb)

XYZ Point Cloud with Labels::

    # Create an Nx4 array with XYZ coordinates and labels
    xyzl = np.zeros((100, 4))
    xyzl[:, :3] = np.random.rand(100, 3)  # XYZ coordinates
    xyzl[:, 3] = 1  # Labels
    
    # Create point cloud with float labels
    pc = pypcd.make_xyz_label_point_cloud(xyzl, label_type='f')
    
    # Or with unsigned integer labels
    pc = pypcd.make_xyz_label_point_cloud(xyzl, label_type='u')

Creating from Numpy Structured Arrays::

    # Create a structured array with custom fields
    dtype = np.dtype([
        ('x', np.float32),
        ('y', np.float32),
        ('z', np.float32),
        ('intensity', np.float32)
    ])
    data = np.zeros(100, dtype=dtype)
    
    # Create point cloud from structured array
    pc = pypcd.PointCloud.from_array(data)

Accessing Point Cloud Data
--------------------------

The point cloud data is stored in a numpy structured array::

    # Access the raw data array
    data = pc.pc_data
    
    # Access specific fields
    x_coords = pc.pc_data['x']
    y_coords = pc.pc_data['y']
    z_coords = pc.pc_data['z']
    
    # Get metadata
    metadata = pc.get_metadata()
    
    # Get number of points
    num_points = pc.points
    
    # Create a deep copy of the point cloud
    pc_copy = pc.copy()
