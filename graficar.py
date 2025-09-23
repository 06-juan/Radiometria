import numpy as np
import matplotlib.pyplot as plt

def graficar_superficie(x, y, z_dicts):
    # Extraemos cada magnitud en listas
    Zx = np.array([d['X'] for d in z_dicts])
    Zy = np.array([d['Y'] for d in z_dicts])
    Zr = np.array([d['R'] for d in z_dicts])
    Zphi = np.array([d['phi'] for d in z_dicts])

    # Convertimos x,y a arrays
    x = np.array(x)
    y = np.array(y)

    # --- Paso clave ---
    # Como es un barrido en malla, reorganizamos en forma de matriz
    x_unique = np.unique(x)
    y_unique = np.unique(y)
    X, Y = np.meshgrid(x_unique, y_unique)

    # Reordenamos Z usando reshape
    nx = len(x_unique)
    ny = len(y_unique)
    Zx = Zx.reshape(ny, nx)
    Zy = Zy.reshape(ny, nx)
    Zr = Zr.reshape(ny, nx)
    Zphi = Zphi.reshape(ny, nx)

    # ---- Gráfica X ----
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111, projection='3d')
    surf1 = ax1.plot_surface(X, Y, Zx, cmap='viridis')
    ax1.set_title("X (In-phase)")
    ax1.set_xlabel("X pos (mm)")
    ax1.set_ylabel("Y pos (mm)")
    ax1.set_zlabel("X (V)")
    fig1.colorbar(surf1, shrink=0.5, aspect=10)

    # ---- Gráfica Y ----
    fig2 = plt.figure()
    ax2 = fig2.add_subplot(111, projection='3d')
    surf2 = ax2.plot_surface(X, Y, Zy, cmap='plasma')
    ax2.set_title("Y (Quadrature)")
    ax2.set_xlabel("X pos (mm)")
    ax2.set_ylabel("Y pos (mm)")
    ax2.set_zlabel("Y (V)")
    fig2.colorbar(surf2, shrink=0.5, aspect=10)

    # ---- Gráfica R ----
    fig3 = plt.figure()
    ax3 = fig3.add_subplot(111, projection='3d')
    surf3 = ax3.plot_surface(X, Y, Zr, cmap='inferno')
    ax3.set_title("R (Magnitude)")
    ax3.set_xlabel("X pos (mm)")
    ax3.set_ylabel("Y pos (mm)")
    ax3.set_zlabel("R (V)")
    fig3.colorbar(surf3, shrink=0.5, aspect=10)

    # ---- Gráfica phi ----
    fig4 = plt.figure()
    ax4 = fig4.add_subplot(111, projection='3d')
    surf4 = ax4.plot_surface(X, Y, Zphi, cmap='cividis')
    ax4.set_title("φ (Phase)")
    ax4.set_xlabel("X pos (mm)")
    ax4.set_ylabel("Y pos (mm)")
    ax4.set_zlabel("φ (deg)")
    fig4.colorbar(surf4, shrink=0.5, aspect=10)

    plt.show()
