const mongoose = require('mongoose');

const canteenSchema = new mongoose.Schema({
    name: {
        type: String,
        required: [true, 'Please add a canteen name'],
        trim: true,
        unique: true
    },
    location: {
        type: String,
        required: [true, 'Please add a location'],
        trim: true
    },
    isOpen: {
        type: Boolean,
        default: false
    },
    isOnlineOrdersEnabled: {
        type: Boolean,
        default: false
    },
    maxBulkSize: {
        type: Number,
        default: 50,
        min: 1
    },
    description: {
        type: String,
        default: ''
    },
    imageUrl: {
        type: String,
        default: ''
    },
    createdAt: {
        type: Date,
        default: Date.now
    }
});

module.exports = mongoose.model('Canteen', canteenSchema);
