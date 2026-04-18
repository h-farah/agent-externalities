// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract MockPriceOracle {
    uint256 public price;

    constructor(uint256 initialPrice) {
        price = initialPrice;
    }

    function setPrice(uint256 newPrice) external {
        price = newPrice;
    }

    function read() external view returns (uint256) {
        return price;
    }
}
