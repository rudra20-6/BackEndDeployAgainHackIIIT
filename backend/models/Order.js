const mongoose = require('mongoose');

const orderItemSchema = new mongoose.Schema({
    menuItem: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'MenuItem',
        required: true
    },
    name: String,
    price: Number,
    quantity: {
        type: Number,
        required: true,
        min: 1
    },
    isVeg: {
        type: Boolean,
        default: true
    }
});

const orderSchema = new mongoose.Schema({
    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true
    },
    canteenId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'Canteen',
        required: true
    },
    items: [orderItemSchema],
    totalAmount: {
        type: Number,
        required: true,
        min: 0
    },
    isBulkOrder: {
        type: Boolean,
        default: false
    },
    status: {
        type: String,
        enum: ['CREATED', 'PAID', 'ACCEPTED', 'PREPARING', 'READY', 'COMPLETED', 'CANCELLED', 'FAILED', 'REFUNDED'],
        default: 'CREATED'
    },
    cancelledBy: {
        type: String,
        enum: ['CANTEEN', 'ADMIN'],
        default: null
    },
    pickupCode: {
        type: String,
        unique: true,
        sparse: true
    },
    pickupCodeUsed: {
        type: Boolean,
        default: false
    },
    specialInstructions: {
        type: String,
        default: ''
    },
    createdAt: {
        type: Date,
        default: Date.now
    },
    updatedAt: {
        type: Date,
        default: Date.now
    }
});

// Generate 6-digit pickup code
orderSchema.methods.generatePickupCode = function () {
    this.pickupCode = Math.floor(100000 + Math.random() * 900000).toString();
    return this.pickupCode;
};

// Update timestamp on save
orderSchema.pre('save', function (next) {
    this.updatedAt = Date.now();
    next();
});

module.exports = mongoose.model('Order', orderSchema);
