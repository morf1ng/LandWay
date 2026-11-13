// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Optional EVM adapter for the demo pre-clearance flow.
/// Document bytes and personal data stay off-chain; only SHA-256 digests are stored.
/// An authorized verifier attests that local document checks passed. This contract
/// does not grant customs clearance or represent a carrier's decision.
contract CorridorPreclearance {
    address public immutable verifier;

    enum Decision { None, NeedsCorrection, ReadyForReview }

    struct Record {
        bytes32 documentDigest;
        Decision decision;
        uint64 updatedAt;
        uint64 revision;
    }

    mapping(bytes32 => Record) public records;

    event ReviewRecorded(
        bytes32 indexed shipmentIdHash,
        bytes32 indexed documentDigest,
        Decision decision,
        uint64 revision
    );

    error OnlyVerifier();
    error EmptyDigest();

    constructor(address verifierAddress) {
        require(verifierAddress != address(0), "zero verifier");
        verifier = verifierAddress;
    }

    function recordReview(bytes32 shipmentIdHash, bytes32 documentDigest, bool checksPassed) external {
        if (msg.sender != verifier) revert OnlyVerifier();
        if (documentDigest == bytes32(0)) revert EmptyDigest();

        Record storage record = records[shipmentIdHash];
        record.documentDigest = documentDigest;
        record.decision = checksPassed ? Decision.ReadyForReview : Decision.NeedsCorrection;
        record.updatedAt = uint64(block.timestamp);
        record.revision += 1;

        emit ReviewRecorded(shipmentIdHash, documentDigest, record.decision, record.revision);
    }
}
