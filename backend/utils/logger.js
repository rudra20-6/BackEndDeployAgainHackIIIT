/**
 * Comprehensive Logger Utility for KMS Backend
 * Logs all requests, responses, errors with timestamps
 */

const colors = {
    reset: '\x1b[0m',
    bright: '\x1b[1m',
    dim: '\x1b[2m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    blue: '\x1b[34m',
    cyan: '\x1b[36m',
};

const Logger = {
    /**
     * Log incoming HTTP request
     */
    logRequest: (req) => {
        const timestamp = new Date().toISOString();
        const divider = `${colors.cyan}${'─'.repeat(70)}${colors.reset}`;
        
        console.log(`\n${divider}`);
        console.log(`${colors.bright}${colors.blue}📥 INCOMING REQUEST${colors.reset}`);
        console.log(`${colors.dim}${timestamp}${colors.reset}`);
        console.log(`${colors.bright}${req.method}${colors.reset} ${colors.cyan}${req.path}${colors.reset}`);
        console.log(`🔗 ${req.protocol.toUpperCase()}://${req.get('host')}${req.path}`);
        
        // Query Parameters
        if (req.query && Object.keys(req.query).length > 0) {
            console.log(`\n${colors.yellow}📋 Query Parameters:${colors.reset}`);
            console.log(JSON.stringify(req.query, null, 2));
        }
        
        // Request Body
        if (req.body && Object.keys(req.body).length > 0) {
            const bodyToLog = { ...req.body };
            if (bodyToLog.password) bodyToLog.password = '***hidden***';
            if (bodyToLog.token) bodyToLog.token = '***hidden***';
            
            console.log(`\n${colors.yellow}📤 Request Body:${colors.reset}`);
            console.log(JSON.stringify(bodyToLog, null, 2));
        }
        
        // Headers
        if (req.headers.authorization) {
            const token = req.headers.authorization.substring(0, 20);
            console.log(`\n${colors.yellow}🔐 Authorization:${colors.reset} Bearer ${token}...`);
        }
    },

    /**
     * Log HTTP response
     */
    logResponse: (req, res, statusCode, duration, data) => {
        const divider = `${colors.cyan}${'─'.repeat(70)}${colors.reset}`;
        const statusColor = statusCode >= 400 ? colors.red : 
                          statusCode >= 300 ? colors.yellow : 
                          colors.green;
        
        console.log(`\n${colors.bright}${colors.green}✅ RESPONSE${colors.reset}`);
        console.log(`${statusColor}Status: ${statusCode}${colors.reset}`);
        console.log(`${colors.cyan}⏱️  Response Time: ${duration}ms${colors.reset}`);
        
        if (data) {
            console.log(`\n${colors.yellow}📊 Response Data:${colors.reset}`);
            const sanitized = JSON.parse(JSON.stringify(data, null, 2));
            if (sanitized?.data?.token) sanitized.data.token = '***hidden***';
            console.log(sanitized);
        }
        
        console.log(`${divider}\n`);
    },

    /**
     * Log errors
     */
    logError: (req, error, statusCode = 500) => {
        const timestamp = new Date().toISOString();
        const divider = `${colors.red}${'█'.repeat(70)}${colors.reset}`;
        
        console.error(`\n${divider}`);
        console.error(`${colors.bright}${colors.red}❌ ERROR OCCURRED${colors.reset}`);
        console.error(`${colors.dim}${timestamp}${colors.reset}`);
        console.error(`📍 ${req.method} ${req.path}`);
        console.error(`${colors.red}Status: ${statusCode}${colors.reset}`);
        console.error(`\n${colors.yellow}Error Message:${colors.reset}`);
        console.error(`${colors.red}${error.message}${colors.reset}`);
        
        if (error.stack) {
            console.error(`\n${colors.yellow}Stack Trace:${colors.reset}`);
            console.error(`${colors.dim}${error.stack}${colors.reset}`);
        }
        
        console.error(`${divider}\n`);
    },

    /**
     * Log database operations
     */
    logDB: (operation, collection, duration, success = true) => {
        const icon = success ? '✅' : '❌';
        const color = success ? colors.green : colors.red;
        console.log(`${color}${icon} DB: ${operation} on ${collection} (${duration}ms)${colors.reset}`);
    },

    /**
     * Log authentication
     */
    logAuth: (action, userId, email, success = true) => {
        const icon = success ? '✅' : '❌';
        const color = success ? colors.green : colors.red;
        console.log(`${color}${icon} Auth: ${action} - User: ${userId || email} ${colors.reset}`);
    },

    /**
     * Log validation errors
     */
    logValidation: (field, error) => {
        console.log(`${colors.yellow}⚠️  Validation Error: ${field}${colors.reset}`);
        console.log(`   ${colors.dim}${error}${colors.reset}`);
    },

    /**
     * Log debug info (only in development)
     */
    debug: (message, data = null) => {
        if (process.env.NODE_ENV === 'development') {
            console.log(`${colors.dim}🐛 DEBUG: ${message}${colors.reset}`);
            if (data) {
                console.log(JSON.stringify(data, null, 2));
            }
        }
    },
};

module.exports = Logger;
