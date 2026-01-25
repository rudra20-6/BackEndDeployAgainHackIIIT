const express = require('express');
const router = express.Router();
const mongoose = require('mongoose');
const Order = require('../models/Order');
const MenuItem = require('../models/MenuItem');
const Canteen = require('../models/Canteen');
const User = require('../models/User'); // Added User import
const { protect, authorize } = require('../middleware/auth');
const { sendPushNotification } = require('../utils/notifications');

// Helper to send order status notification
const sendOrderNotification = async (orderId, status, message) => {
    try {
        const order = await Order.findById(orderId).populate('userId');
        if (!order || !order.userId || !order.userId.pushToken) return;

        await sendPushNotification(
            order.userId.pushToken,
            `Order Update: ${status}`,
            message,
            { orderId: order._id, status: status }
        );
    } catch (err) {
        console.error('Notification error:', err);
    }
};


// @route   POST /api/orders
// @desc    Create new order
// @access  Private (Student)
router.post('/', protect, async (req, res) => {
    try {
        const { canteenId, items, specialInstructions } = req.body;

        // Verify canteen exists and is open
        const canteen = await Canteen.findById(canteenId);
        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        if (!canteen.isOpen) {
            return res.status(400).json({
                success: false,
                message: 'Canteen is currently closed'
            });
        }

        if (!canteen.isOnlineOrdersEnabled) {
            return res.status(400).json({
                success: false,
                message: 'Online orders are currently disabled for this canteen'
            });
        }

        // Calculate total and validate items
        let totalAmount = 0;
        let totalQuantity = 0;
        const orderItems = [];

        for (const item of items) {
            const menuItem = await MenuItem.findById(item.menuItem);

            if (!menuItem) {
                return res.status(404).json({
                    success: false,
                    message: `Menu item ${item.menuItem} not found`
                });
            }

            if (!menuItem.isAvailable) {
                return res.status(400).json({
                    success: false,
                    message: `${menuItem.name} is currently unavailable`
                });
            }

            if (menuItem.canteenId.toString() !== canteenId) {
                return res.status(400).json({
                    success: false,
                    message: `${menuItem.name} does not belong to this canteen`
                });
            }

            const itemTotal = menuItem.price * item.quantity;
            totalAmount += itemTotal;
            totalQuantity += item.quantity;

            orderItems.push({
                menuItem: menuItem._id,
                name: menuItem.name,
                price: menuItem.price,
                quantity: item.quantity,
                isVeg: menuItem.isVeg
            });
        }

        // Check if bulk order
        const isBulkOrder = totalQuantity > canteen.maxBulkSize;

        // Create order
        const order = await Order.create({
            userId: req.user._id,
            canteenId,
            items: orderItems,
            totalAmount,
            isBulkOrder,
            specialInstructions,
            status: 'CREATED'
        });

        // Compute simple queue status & ETA (not persisted)
        const activeStatuses = ['PAID', 'ACCEPTED', 'PREPARING'];
        const activeOrders = await Order.find({ canteenId, status: { $in: activeStatuses } }).select('isBulkOrder').lean();
        const weightedQueueUnits = activeOrders.reduce((acc, o) => acc + (o.isBulkOrder ? 2 : 1), 0) + (isBulkOrder ? 2 : 1);
        const estimatedWaitMinutes = weightedQueueUnits * 3; // 3 min per unit

        res.status(201).json({
            success: true,
            data: order,
            meta: {
                queuePosition: activeOrders.length + 1,
                estimatedWaitMinutes,
                demandHint: weightedQueueUnits >= 15 ? 'HIGH' : weightedQueueUnits >= 8 ? 'MEDIUM' : 'LOW'
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/orders/my
// @desc    Get current user's orders
// @access  Private
router.get('/my', protect, async (req, res) => {
    try {
        const orders = await Order.find({ userId: req.user._id })
            .populate('canteenId', 'name location')
            .populate({
                path: 'items.menuItem',
                select: 'isVeg'
            })
            .sort('-createdAt')
            .lean();

        // Backfill isVeg from menuItem if missing (for legacy orders)
        orders.forEach(order => {
            if (order.items) {
                order.items.forEach(item => {
                    if (item.isVeg === undefined && item.menuItem && item.menuItem.isVeg !== undefined) {
                        item.isVeg = item.menuItem.isVeg;
                    }
                });
            }
        });

        res.json({
            success: true,
            count: orders.length,
            data: orders
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/orders/all
// @desc    Get all orders (Admin only)
// @access  Private (Admin)
router.get('/all', protect, authorize('ADMIN'), async (req, res) => {
    try {
        const { status } = req.query;
        const query = {};
        if (status) {
            query.status = status;
        }

        const orders = await Order.find(query)
            .populate('userId', 'name email')
            .populate('canteenId', 'name location')
            .sort('-createdAt');

        res.json({
            success: true,
            count: orders.length,
            data: orders
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/orders/canteen/:canteenId
// @desc    Get orders for a canteen
// @access  Private (Canteen owner or Admin)
router.get('/canteen/:canteenId', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== req.params.canteenId) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to view orders for this canteen'
            });
        }

        const { status } = req.query;
        const query = { canteenId: req.params.canteenId };

        // Only show paid orders to canteen
        if (status) {
            query.status = status;
        } else {
            query.status = { $in: ['PAID', 'ACCEPTED', 'PREPARING', 'READY'] };
        }

        const orders = await Order.find(query)
            .populate('userId', 'name email')
            .sort('-createdAt');

        res.json({
            success: true,
            count: orders.length,
            data: orders
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/orders/canteen/:canteenId/completed
// @desc    Get completed orders for a canteen with earnings statistics
// @access  Private (Canteen owner or Admin)
router.get('/canteen/:canteenId/completed', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== req.params.canteenId) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to view orders for this canteen'
            });
        }

        // Fetch all completed and cancelled orders
        const completedOrders = await Order.find({
            canteenId: req.params.canteenId,
            status: { $in: ['COMPLETED', 'CANCELLED', 'REFUNDED'] }
        })
            .populate('userId', 'name email')
            .sort('-createdAt');

        // Calculate earnings for today
        const startOfDay = new Date();
        startOfDay.setHours(0, 0, 0, 0);

        const endOfDay = new Date();
        endOfDay.setHours(23, 59, 59, 999);

        const dailyEarnings = await Order.aggregate([
            {
                $match: {
                    canteenId: new mongoose.Types.ObjectId(req.params.canteenId),
                    status: 'COMPLETED',
                    updatedAt: { $gte: startOfDay, $lte: endOfDay }
                }
            },
            {
                $group: {
                    _id: null,
                    total: { $sum: '$totalAmount' }
                }
            }
        ]);

        // Calculate earnings for current month
        const startOfMonth = new Date();
        startOfMonth.setDate(1);
        startOfMonth.setHours(0, 0, 0, 0);

        const endOfMonth = new Date();
        endOfMonth.setMonth(endOfMonth.getMonth() + 1);
        endOfMonth.setDate(0);
        endOfMonth.setHours(23, 59, 59, 999);

        const monthlyEarnings = await Order.aggregate([
            {
                $match: {
                    canteenId: new mongoose.Types.ObjectId(req.params.canteenId),
                    status: 'COMPLETED',
                    updatedAt: { $gte: startOfMonth, $lte: endOfMonth }
                }
            },
            {
                $group: {
                    _id: null,
                    total: { $sum: '$totalAmount' }
                }
            }
        ]);

        res.json({
            success: true,
            count: completedOrders.length,
            data: completedOrders,
            earnings: {
                daily: dailyEarnings.length > 0 ? dailyEarnings[0].total : 0,
                monthly: monthlyEarnings.length > 0 ? monthlyEarnings[0].total : 0
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/orders/:id
// @desc    Get single order
// @access  Private
router.get('/:id', protect, async (req, res) => {
    try {
        const order = await Order.findById(req.params.id)
            .populate('canteenId', 'name location')
            .populate('userId', 'name email');

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Check authorization
        if (req.user.role === 'STUDENT' && order.userId._id.toString() !== req.user._id.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to view this order'
            });
        }

        if (req.user.role === 'CANTEEN' && order.canteenId._id.toString() !== req.user.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to view this order'
            });
        }

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/orders/:id/accept
// @desc    Accept an order
// @access  Private (Canteen owner)
router.post('/:id/accept', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const order = await Order.findById(req.params.id);

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== order.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this order'
            });
        }

        if (order.status !== 'PAID') {
            return res.status(400).json({
                success: false,
                message: 'Only paid orders can be accepted'
            });
        }

        order.status = 'ACCEPTED';
        await order.save();

        // Send notification
        sendOrderNotification(order._id, 'Accepted', 'Your order has been accepted and is in queue.');

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/orders/:id/prepare
// @desc    Mark order as preparing
// @access  Private (Canteen owner)
router.post('/:id/prepare', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const order = await Order.findById(req.params.id);

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== order.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this order'
            });
        }

        if (order.status !== 'ACCEPTED') {
            return res.status(400).json({
                success: false,
                message: 'Only accepted orders can be marked as preparing'
            });
        }

        order.status = 'PREPARING';
        await order.save();

        // Send notification
        sendOrderNotification(order._id, 'Preparing', 'Your food is being prepared!');

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/orders/:id/ready
// @desc    Mark order as ready for pickup
// @access  Private (Canteen owner)
router.post('/:id/ready', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const order = await Order.findById(req.params.id);

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== order.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this order'
            });
        }

        if (order.status !== 'PREPARING') {
            return res.status(400).json({
                success: false,
                message: 'Only preparing orders can be marked as ready'
            });
        }

        // Generate pickup code if not already generated
        if (!order.pickupCode) {
            order.generatePickupCode();
        }

        order.status = 'READY';
        await order.save();

        // Send notification (include pickup code)
        sendOrderNotification(
            order._id, 
            'Ready for Pickup', 
            `Your order is ready! Pickup Code: ${order.pickupCode}`
        );

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/orders/:id/complete
// @desc    Complete order with pickup code
// @access  Private (Canteen owner)
router.post('/:id/complete', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const { pickupCode } = req.body;
        const order = await Order.findById(req.params.id);

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== order.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this order'
            });
        }

        if (order.status !== 'READY') {
            return res.status(400).json({
                success: false,
                message: 'Only ready orders can be completed'
            });
        }

        if (order.pickupCodeUsed) {
            return res.status(400).json({
                success: false,
                message: 'Pickup code already used'
            });
        }

        if (order.pickupCode !== pickupCode) {
            return res.status(400).json({
                success: false,
                message: 'Invalid pickup code'
            });
        }

        order.status = 'COMPLETED';
        order.pickupCodeUsed = true;
        await order.save();

        // Send notification
        sendOrderNotification(order._id, 'Completed', 'Order picked up. Enjoy your meal!');

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/orders/:id/cancel
// @desc    Cancel an order
// @access  Private
router.post('/:id/cancel', protect, async (req, res) => {
    try {
        const order = await Order.findById(req.params.id);

        if (!order) {
            return res.status(404).json({
                success: false,
                message: 'Order not found'
            });
        }

        // Determine who is cancelling
        let cancelledBy = 'USER';
        if (req.user.role === 'CANTEEN') {
            cancelledBy = 'CANTEEN';
            // Check if user is canteen owner of this order
            if (order.canteenId.toString() !== req.user.canteenId.toString()) {
                return res.status(403).json({
                    success: false,
                    message: 'Not authorized to cancel this order'
                });
            }
        } else if (req.user.role === 'ADMIN') {
            cancelledBy = 'ADMIN';
        } else {
            // Students are not allowed to cancel orders
            return res.status(403).json({
                success: false,
                message: 'Students cannot cancel orders. Please contact the canteen.'
            });
        }

        // Logic for cancellation eligibility
        if (cancelledBy === 'USER') {
            // This block should ideally not be reached if students are blocked, but kept for safeguards/other roles
            if (['PREPARING', 'READY', 'COMPLETED', 'CANCELLED'].includes(order.status)) {
                return res.status(400).json({
                    success: false,
                    message: 'Cannot cancel order at this stage'
                });
            }
        } else {
            // Canteens/Admins can cancel anytime before completion (except already cancelled)
            if (['COMPLETED', 'CANCELLED'].includes(order.status)) {
                return res.status(400).json({
                    success: false,
                    message: 'Cannot cancel order that is already completed or cancelled'
                });
            }
        }

        order.status = 'CANCELLED';
        order.cancelledBy = cancelledBy;
        await order.save();

        // Send notification
        sendOrderNotification(order._id, 'Cancelled', 'Your order was cancelled.');

        // Auto-refund demo logic
        if (order.status === 'CANCELLED' && cancelledBy === 'CANTEEN') {
            const orderId = order._id;
            console.log(`Order ${orderId} cancelled by canteen. Scheduling auto-refund in 30s...`);
            setTimeout(async () => {
                try {
                    const orderToRefund = await Order.findById(orderId);
                    if (orderToRefund && orderToRefund.status === 'CANCELLED') {
                        orderToRefund.status = 'REFUNDED';
                        await orderToRefund.save();
                        console.log(`Order ${orderId} auto-refunded.`);
                        
                        // Send notification
                        sendOrderNotification(orderId, 'Refunded', 'Your order has been refunded.');
                    }
                } catch (err) {
                    console.error(`Error auto-refunding order ${orderId}:`, err);
                }
            }, 30000); // 30 seconds
        }

        res.json({
            success: true,
            data: order
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

module.exports = router;
