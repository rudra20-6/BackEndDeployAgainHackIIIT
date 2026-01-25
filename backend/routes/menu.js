const express = require('express');
const router = express.Router();
const MenuItem = require('../models/MenuItem');
const Canteen = require('../models/Canteen');
const { protect, authorize } = require('../middleware/auth');

// @route   GET /api/menu/canteen/:canteenId
// @desc    Get menu for a canteen
// @access  Public
router.get('/canteen/:canteenId', async (req, res) => {
    try {
        const menuItems = await MenuItem.find({ canteenId: req.params.canteenId });
        res.json({
            success: true,
            count: menuItems.length,
            data: menuItems
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   GET /api/menu/:id
// @desc    Get single menu item
// @access  Public
router.get('/:id', async (req, res) => {
    try {
        const menuItem = await MenuItem.findById(req.params.id);

        if (!menuItem) {
            return res.status(404).json({
                success: false,
                message: 'Menu item not found'
            });
        }

        res.json({
            success: true,
            data: menuItem
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   POST /api/menu
// @desc    Create new menu item
// @access  Private (Canteen owner or Admin)
router.post('/', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const { canteenId } = req.body;

        console.log('➕ Create menu item request:', {
            requestedCanteenId: canteenId,
            userRole: req.user.role,
            userCanteenId: req.user.canteenId,
            match: req.user.canteenId?.toString() === canteenId
        });

        // Verify canteen exists
        const canteen = await Canteen.findById(canteenId);
        if (!canteen) {
            return res.status(404).json({
                success: false,
                message: 'Canteen not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== canteenId) {
            console.log('❌ Authorization failed - canteenId mismatch for menu creation');
            return res.status(403).json({
                success: false,
                message: 'Not authorized to add items to this canteen'
            });
        }

        const menuItem = await MenuItem.create(req.body);
        res.status(201).json({
            success: true,
            data: menuItem
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   PUT /api/menu/:id
// @desc    Update menu item
// @access  Private (Canteen owner or Admin)
router.put('/:id', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        let menuItem = await MenuItem.findById(req.params.id);

        if (!menuItem) {
            return res.status(404).json({
                success: false,
                message: 'Menu item not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== menuItem.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this menu item'
            });
        }

        menuItem = await MenuItem.findByIdAndUpdate(req.params.id, req.body, {
            new: true,
            runValidators: true
        });

        res.json({
            success: true,
            data: menuItem
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   PATCH /api/menu/:id/toggle-availability
// @desc    Toggle menu item availability
// @access  Private (Canteen owner or Admin)
router.patch('/:id/toggle-availability', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const menuItem = await MenuItem.findById(req.params.id);

        if (!menuItem) {
            return res.status(404).json({
                success: false,
                message: 'Menu item not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== menuItem.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to update this menu item'
            });
        }

        menuItem.isAvailable = !menuItem.isAvailable;
        await menuItem.save();

        res.json({
            success: true,
            data: menuItem
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: error.message
        });
    }
});

// @route   DELETE /api/menu/:id
// @desc    Delete menu item
// @access  Private (Canteen owner or Admin)
router.delete('/:id', protect, authorize('CANTEEN', 'ADMIN'), async (req, res) => {
    try {
        const menuItem = await MenuItem.findById(req.params.id);

        if (!menuItem) {
            return res.status(404).json({
                success: false,
                message: 'Menu item not found'
            });
        }

        // Check if user is canteen owner
        if (req.user.role === 'CANTEEN' && req.user.canteenId.toString() !== menuItem.canteenId.toString()) {
            return res.status(403).json({
                success: false,
                message: 'Not authorized to delete this menu item'
            });
        }

        await menuItem.deleteOne();

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
