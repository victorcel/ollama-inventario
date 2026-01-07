-- init-db.sql
-- Activar la extensión pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla de productos del inventario
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    categoria VARCHAR(100),
    precio DECIMAL(10, 2),
    stock INTEGER DEFAULT 0,
    ubicacion VARCHAR(100),
    proveedor VARCHAR(255),
    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN DEFAULT true
);

-- Tabla para almacenar embeddings de productos
CREATE TABLE producto_embeddings (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER REFERENCES productos(id) ON DELETE CASCADE,
    embedding vector(384),  -- all-minilm genera vectores de 384 dimensiones
    texto_embebido TEXT,     -- Texto que se usó para generar el embedding
    fecha_generacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(producto_id)
);

-- Índice para búsqueda vectorial rápida (IVFFlat)
CREATE INDEX idx_producto_embeddings_vector
ON producto_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Índice para búsquedas por producto
CREATE INDEX idx_producto_embeddings_producto_id
ON producto_embeddings(producto_id);

-- Índices para optimizar búsquedas en productos
CREATE INDEX idx_productos_codigo ON productos(codigo);
CREATE INDEX idx_productos_categoria ON productos(categoria);
CREATE INDEX idx_productos_activo ON productos(activo);

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION actualizar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar automáticamente fecha_actualizacion
CREATE TRIGGER trigger_actualizar_productos
    BEFORE UPDATE ON productos
    FOR EACH ROW
    EXECUTE FUNCTION actualizar_timestamp();

-- Función para búsqueda semántica de productos
CREATE OR REPLACE FUNCTION buscar_productos_similares(
    query_embedding vector(384),
    limite INTEGER DEFAULT 10
)
RETURNS TABLE (
    producto_id INTEGER,
    codigo VARCHAR,
    nombre VARCHAR,
    descripcion TEXT,
    similitud FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id,
        p.codigo,
        p.nombre,
        p.descripcion,
        1 - (pe.embedding <=> query_embedding) as similitud
    FROM producto_embeddings pe
    JOIN productos p ON pe.producto_id = p.id
    WHERE p.activo = true
    ORDER BY pe.embedding <=> query_embedding
    LIMIT limite;
END;
$$ LANGUAGE plpgsql;

-- Insertar algunos datos de ejemplo
INSERT INTO productos (codigo, nombre, descripcion, categoria, precio, stock, ubicacion, proveedor) VALUES
('PROD-001', 'Laptop Dell XPS 13', 'Laptop ultradelgada 13 pulgadas, Intel i7, 16GB RAM', 'Electrónica', 1299.99, 15, 'Almacén A-1', 'Dell Inc'),
('PROD-002', 'Mouse Inalámbrico Logitech', 'Mouse ergonómico inalámbrico con conexión Bluetooth', 'Accesorios', 29.99, 50, 'Almacén B-2', 'Logitech'),
('PROD-003', 'Teclado Mecánico RGB', 'Teclado mecánico retroiluminado RGB switches azules', 'Accesorios', 89.99, 30, 'Almacén B-2', 'Corsair'),
('PROD-004', 'Monitor LG 27 pulgadas', 'Monitor IPS 27 pulgadas 4K resolución HDR', 'Electrónica', 449.99, 20, 'Almacén A-1', 'LG Electronics'),
('PROD-005', 'Silla Ergonómica Oficina', 'Silla de oficina ergonómica con soporte lumbar ajustable', 'Muebles', 199.99, 10, 'Almacén C-3', 'Herman Miller');

-- Comentario sobre la configuración
COMMENT ON TABLE producto_embeddings IS 'Almacena embeddings vectoriales de productos para búsqueda semántica';