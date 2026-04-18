// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IPriceOracle {
    function read() external view returns (uint256);
}

contract ToyLendingProtocol {
    uint256 public constant BPS = 10_000;
    uint256 public constant SCALE = 1e18;
    uint256 public constant COLLATERAL_FACTOR_BPS = 8_000;
    uint256 public constant LIQUIDATION_BONUS_BPS = 500;
    uint256 public constant CLOSE_FACTOR_BPS = 5_000;

    IPriceOracle public immutable oracle;

    struct Position {
        uint256 collateralUnits;
        uint256 debtUsd;
    }

    constructor(address oracle_) {
        oracle = IPriceOracle(oracle_);
    }

    function collateralValue(Position memory position) public view returns (uint256) {
        return (position.collateralUnits * oracle.read()) / SCALE;
    }

    function maxBorrow(Position memory position) public view returns (uint256) {
        return (collateralValue(position) * COLLATERAL_FACTOR_BPS) / BPS;
    }

    function isUndercollateralized(Position memory position) public view returns (bool) {
        return position.debtUsd > maxBorrow(position);
    }

    function maxLiquidatable(Position memory position) public pure returns (uint256) {
        return (position.debtUsd * CLOSE_FACTOR_BPS) / BPS;
    }

    function seizeUnits(uint256 repayAmount) public view returns (uint256) {
        uint256 seizeValue = (repayAmount * (BPS + LIQUIDATION_BONUS_BPS)) / BPS;
        return (seizeValue * SCALE) / oracle.read();
    }

    function canLiquidate(Position memory position, uint256 repayAmount) external view returns (bool) {
        return isUndercollateralized(position) && repayAmount > 0 && repayAmount <= maxLiquidatable(position);
    }

    function simulateLiquidation(
        Position memory position,
        uint256 repayAmount
    ) external view returns (uint256 remainingCollateralUnits, uint256 remainingDebtUsd, uint256 collateralSeizedUnits) {
        collateralSeizedUnits = seizeUnits(repayAmount);
        require(collateralSeizedUnits <= position.collateralUnits, "insufficient collateral");

        remainingCollateralUnits = position.collateralUnits - collateralSeizedUnits;
        remainingDebtUsd = position.debtUsd - repayAmount;
    }
}
