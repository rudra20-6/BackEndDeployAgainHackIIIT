require('dotenv').config();
const express = require('express');
const cors = require('cors');
const connectDB = require('./config/db');

// Initialize express
const app = express();

// Connect to database
connectDB();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// 🔍 Request Logging Middleware
app.use((req, res, next) => {
    const startTime = Date.now();
    const requestId = `[${new Date().toISOString()}]`;

    // Log incoming request
    console.log(`\n${requestId} ─────────────────────────────────────────`);
    console.log(`📥 ${req.method} ${req.path}`);
    console.log(`🔗 Full URL: ${req.method} ${req.protocol}://${req.get('host')}${req.path}`);

    if (req.query && Object.keys(req.query).length > 0) {
        console.log(`📋 Query Params:`, JSON.stringify(req.query, null, 2));
    }

    if (req.body && Object.keys(req.body).length > 0) {
        // Don't log passwords
        const bodyToLog = { ...req.body };
        if (bodyToLog.password) bodyToLog.password = '***hidden***';
        console.log(`📤 Request Body:`, JSON.stringify(bodyToLog, null, 2));
    }

    if (req.headers.authorization) {
        console.log(`🔐 Authorization: Bearer ${req.headers.authorization.substring(0, 20)}...`);
    }

    // Capture the original res.json and res.send methods
    const originalJson = res.json.bind(res);
    const originalSend = res.send.bind(res);
    let responseData = null;

    res.json = function (data) {
        responseData = data;
        const duration = Date.now() - startTime;
        console.log(`\n✅ Response Status: ${res.statusCode}`);
        console.log(`⏱️  Response Time: ${duration}ms`);
        console.log(`📊 Response Data:`, JSON.stringify(data, null, 2));
        console.log(`${requestId} ─────────────────────────────────────────\n`);
        return originalJson(data);
    };

    res.send = function (data) {
        const duration = Date.now() - startTime;
        console.log(`\n✅ Response Status: ${res.statusCode}`);
        console.log(`⏱️  Response Time: ${duration}ms`);
        console.log(`📊 Response Data:`, data);
        console.log(`${requestId} ─────────────────────────────────────────\n`);
        return originalSend(data);
    };

    next();
});

// Routes
app.use('/api/auth', require('./routes/auth'));
app.use('/api/canteens', require('./routes/canteens'));
app.use('/api/menu', require('./routes/menu'));
app.use('/api/orders', require('./routes/orders'));
app.use('/api/payments', require('./routes/payments'));

// Health check
app.get('/health', (req, res) => {
    res.json({
        success: true,
        message: 'KMS Backend is running',
        timestamp: new Date().toISOString()
    });
});

// Root route
app.get('/', (req, res) => {
    res.json({
        success: true,
        message: 'Welcome to Khana Management System API',
        version: '1.0.0',
        endpoints: {
            auth: '/api/auth',
            canteens: '/api/canteens',
            menu: '/api/menu',
            orders: '/api/orders',
            payments: '/api/payments'
        }
    });
});

// Error handler with logging
app.use((err, req, res, next) => {
    const errorId = `[${new Date().toISOString()}]`;
    console.error(`\n${errorId} ❌ ERROR ❌`);
    console.error(`📍 Endpoint: ${req.method} ${req.path}`);
    console.error(`📋 Error Message:`, err.message);
    console.error(`📚 Stack:`, err.stack);
    console.error(`${errorId} ─────────────────────────────────────────\n`);

    res.status(500).json({
        success: false,
        message: 'Something went wrong!',
        error: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
});

// 404 handler
app.use((req, res) => {
    console.warn(`\n⚠️  404 Not Found: ${req.method} ${req.path}\n`);
    res.status(404).json({
        success: false,
        message: 'Route not found'
    });
});

// Log registered routes
console.log('Registered routes:');
app._router.stack
  .filter(r => r.route && r.route.path)
  .forEach(r => {
    const methods = Object.keys(r.route.methods).map(m => m.toUpperCase()).join(', ');
    console.log(methods, r.route.path);
  });

const PORT = process.env.PORT || 5000;

app.listen(PORT, () => {
    console.log(`\n🚀 KMS Backend Server running on port ${PORT}`);
    console.log(`📍 API URL: http://localhost:${PORT}`);
    console.log(`🏥 Health Check: http://localhost:${PORT}/health`);
    console.log(`📝 Request logging enabled - All requests will be logged below\n`);
});

