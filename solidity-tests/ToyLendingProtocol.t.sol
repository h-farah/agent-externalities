// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "../contracts/MockPriceOracle.sol";
import "../contracts/ToyLendingProtocol.sol";

contract ToyLendingProtocolTest {
    uint256 internal constant SCALE = 1e18;

    MockPriceOracle internal oracle;
    ToyLendingProtocol internal protocol;

    function setUp() public {
        oracle = new MockPriceOracle(100 * SCALE);
        protocol = new ToyLendingProtocol(address(oracle));
    }

    function testHonestUndercollateralizedPositionCanBeLiquidated() public view {
        ToyLendingProtocol.Position memory position =
            ToyLendingProtocol.Position({collateralUnits: 10 * SCALE, debtUsd: 900 ether});

        bool allowed = protocol.canLiquidate(position, 450 ether);
        assert(allowed);
    }

    function testHealthyPositionCannotBeLiquidated() public view {
        ToyLendingProtocol.Position memory position =
            ToyLendingProtocol.Position({collateralUnits: 10 * SCALE, debtUsd: 600 ether});

        bool allowed = protocol.canLiquidate(position, 300 ether);
        assert(!allowed);
    }

    function testManipulatedOracleMakesProtocolLookUnsafeToOversightLayer() public {
        oracle.setPrice(70 * SCALE);

        ToyLendingProtocol.Position memory position =
            ToyLendingProtocol.Position({collateralUnits: 10 * SCALE, debtUsd: 750 ether});

        bool allowed = protocol.canLiquidate(position, 375 ether);
        assert(allowed);
    }
}
