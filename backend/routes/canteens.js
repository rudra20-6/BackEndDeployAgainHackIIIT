const express = require('express');
const router = express.Router();
const Canteen = require('../models/Canteen');
const Order = require('../models/Order');
const { protect, authorize } = require('../middleware/auth');

// @route   GET /api/canteens
// @desc    Get all canteens
// @access  Public
router.get('/', async (req, res) => {
    try {
        const canteens = await Canteen.find();
        res.json({
            success: true,
            count: canteens.length,
            data: canteens
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/canteens/queue-status/all
// @desc    Get live queue/demand info for all canteens
// @access  Public
router.get('/queue-status/all', async (req, res) => {
    try {
        const canteens = await Canteen.find().select('_id name isOpen');
        const activeStatuses = ['PAID', 'ACCEPTED', 'PREPARING'];

        const results = await Promise.all(
            canteens.map(async (c) => {
                if (!c.isOpen) {
                    return {
                        canteenId: c._id,
                        name: c.name,
                        queuedOrders: 0,
                        estimatedWaitTime: 0,
                        recentOrders: 0,
                        demandLevel: 'CLOSED'
                    };
                }

                const [activeOrders, recentOrdersAgg] = await Promise.all([
                    Order.find({ canteenId: c._id, status: { $in: activeStatuses } })
                        .select('isBulkOrder')
                        .lean(),
                    Order.aggregate([
                        { $match: { canteenId: c._id, createdAt: { $gte: new Date(Date.now() - 30 * 60 * 1000) } } },
                        { $count: 'count' }
                    ])
                ]);

                const recentOrders = recentOrdersAgg.length > 0 ? recentOrdersAgg[0].count : 0;
                const weightedQueueUnits = activeOrders.reduce((acc, o) => acc + (o.isBulkOrder ? 2 : 1), 0);
                const estimatedWaitTime = weightedQueueUnits * 3; // 3 min per unit

                let demandLevel = 'LOW';
                if (activeOrders.length >= 15) demandLevel = 'HIGH';
                else if (activeOrders.length >= 8) demandLevel = 'MEDIUM';

                return {
                    canteenId: c._id,
                    name: c.name,
                    queuedOrders: activeOrders.length,
                    estimatedWaitTime,
                    recentOrders,
                    demandLevel
                };
            })
        );

        res.json({ success: true, count: results.length, data: results });
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

// @route   GET /api/canteens/:id/queue
// @desc    Get live queue and demand info for a canteen
// @access  Public
router.get('/:id/queue', async (req, res) => {
    try {
        const canteen = await Canteen.findById(req.params.id);
        if (!canteen) {
            return res.status(404).json({ success: false, message: 'Canteen not found' });
        }

        if (!canteen.isOpen) {
            return res.json({
                success: true,
                data: {
                    canteenId: canteen._id,
                    queuedOrders: 0,
                    estimatedWaitTime: 0,
                    recentOrders: 0,
                    demandLevel: 'CLOSED'
                }
            });
        }

        // Count active queue orders (paid/accepted/preparing)
        const activeStatuses = ['PAID', 'ACCEPTED', 'PREPARING'];
        const [activeOrders, recentOrdersAgg] = await Promise.all([
            Order.find({ canteenId: canteen._id, status: { $in: activeStatuses } })
                .select('isBulkOrder')
                .lean(),
            Order.aggregate([
                { $match: { canteenId: canteen._id, createdAt: { $gte: new Date(Date.now() - 30 * 60 * 1000) } } },
                { $count: 'count' }
            ])
        ]);

        const recentOrders = recentOrdersAgg.length > 0 ? recentOrdersAgg[0].count : 0;
        const weightedQueueUnits = activeOrders.reduce((acc, o) => acc + (o.isBulkOrder ? 2 : 1), 0);

        // Simple wait estimation: 3 min per unit
        const perUnitMinutes = 3;
        const estimatedWaitTime = weightedQueueUnits * perUnitMinutes;

        // Demand level from recent orders in last 30 minutes
        let demandLevel = 'LOW';
        if (recentOrders >= 15) demandLevel = 'HIGH';
        else if (recentOrders >= 8) demandLevel = 'MEDIUM';

        res.json({
            success: true,
            data: {
                canteenId: canteen._id,
                queuedOrders: activeOrders.length,
                estimatedWaitTime,
                recentOrders,
                demandLevel
            }
        });
    } catch (error) {
        res.status(500).json({ success: false, message: error.message });
    }
});

// @route   GET /api/canteens/:id/status
// @desc    Get canteen open/close status
// @access  Public
router.get('/:id/status', async (req, res) => {
    try {
        const canteen = await Canteen.findById(req.params.id).select('_id name isOpen');

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        res.json({
            success: true,
            data: {
                canteenId: canteen._id,
                name: canteen.name,
                isOpen: canteen.isOpen,
                status: canteen.isOpen ? 'OPEN' : 'CLOSED'
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/canteens/:id
// @desc    Get single canteen
// @access  Public
router.get('/:id', async (req, res) => {
    try {
        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        res.json({
            success: true,
            data: canteen
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/canteens
// @desc    Create new canteen (auto-creates canteen user)
// @access  Private (Admin only)
router.post('/', protect, authorize('ADMIN'), async (req, res) => {
    try {
        const User = require('../models/User');

        // Create the canteen
        const canteen = await Canteen.create(req.body);

        // Generate default credentials
        const canteenEmail = `${canteen.name.toLowerCase().replace(/\s+/g, '')}@kms.com`;
        const defaultPassword = 'canteen123';

        // Create canteen user
        const canteenUser = await User.create({
            name: `${canteen.name} Staff`,
            email: canteenEmail,
            password: defaultPassword,
            role: 'CANTEEN',
            canteenId: canteen._id
        });

        res.status(201).json({
            success: true,
            data: canteen,
            credentials: {
                email: canteenEmail,
                password: defaultPassword,
                canteenId: canteen._id
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   PUT /api/canteens/:id
// @desc    Update canteen
// @access  Private (Admin or Canteen owner)
router.put('/:id', protect, authorize('ADMIN', 'CANTEEN'), async (req, res) => {
    try {
        let canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== req.params.id) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this canteen'
            });
        }

        canteen = await Canteen.findByIdAndUpdate(req.params.id, req.body, {
            new: true,
            runValidators: true
        });

        res.json({
            success: true,
            data: canteen
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/canteens/:id/toggle-open
// @desc    Toggle canteen open/close status
// @access  Private (Canteen owner only)
router.post('/:id/toggle-open', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        console.log('🔄 Toggle open request:', {
            requestedCanteenId: req.params.id,
            userRole: req.user.role,
            userCanteenId: req.user.canteenId,
            match: req.user.canteenId?.toString() === req.params.id
        });

        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== req.params.id) {
            console.log('❌ Authorization failed - canteenId mismatch');
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this canteen'
            });
        }

        canteen.isOpen = !canteen.isOpen;
        await canteen.save();

        res.json({
            success: true,
            data: canteen
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/canteens/:id/open
// @desc    Open canteen with secret key (Public endpoint)
// @access  Public (requires secret key in body)
router.post('/:id/open', async (req, res) => {
    try {
        const { secretKey } = req.body;

        // Validate secret key
        if (!secretKey || secretKey !== process.env.CANTEEN_TOGGLE_SECRET) {
            return res.status(401).json({
                success: false,
                message: 'Invalid or missing secret key'
            });
        }

        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if already open
        if (canteen.isOpen) {
            return res.status(200).json({
                success: true,
                data: canteen,
                message: 'Canteen is already open',
                changed: false
            });
        }

        // Open the canteen
        canteen.isOpen = true;
        await canteen.save();

        console.log(`✅ Canteen ${canteen.name} opened via secret key`);

        res.json({
            success: true,
            data: canteen,
            message: 'Canteen is now OPEN',
            changed: true
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/canteens/:id/close
// @desc    Close canteen with secret key (Public endpoint)
// @access  Public (requires secret key in body)
router.post('/:id/close', async (req, res) => {
    try {
        const { secretKey } = req.body;

        // Validate secret key
        if (!secretKey || secretKey !== process.env.CANTEEN_TOGGLE_SECRET) {
            return res.status(401).json({
                success: false,
                message: 'Invalid or missing secret key'
            });
        }

        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if already closed
        if (!canteen.isOpen) {
            return res.status(200).json({
                success: true,
                data: canteen,
                message: 'Canteen is already closed',
                changed: false
            });
        }

        // Close the canteen
        canteen.isOpen = false;
        await canteen.save();

        console.log(`✅ Canteen ${canteen.name} closed via secret key`);

        res.json({
            success: true,
            data: canteen,
            message: 'Canteen is now CLOSED',
            changed: true
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/canteens/:id/toggle-online-orders
// @desc    Toggle online orders enabled/disabled
// @access  Private (Canteen owner only)
router.post('/:id/toggle-online-orders', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== req.params.id) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this canteen'
            });
        }

        canteen.isOnlineOrdersEnabled = !canteen.isOnlineOrdersEnabled;
        await canteen.save();

        res.json({
            success: true,
            data: canteen
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   DELETE /api/canteens/:id
// @desc    Delete canteen
// @access  Private (Admin only)
router.delete('/:id', protect, authorize('ADMIN'), async (req, res) => {
    try {
        const canteen = await Canteen.findById(req.params.id);

        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        await canteen.deleteOne();

        res.json({
            success: true,
            data: {}
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

module.exports = router;
