import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
	id: root
	title: qsTr("Bulk recharge")
	property string settingsPrefix: "com.victronenergy.settings/Settings/Ess3Policy"
	model: VisualItemModel {
		MbSpinBox {
			id: idCurrentBatteryBulkRecharge
			description: qsTr("Target battery charge current")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/CurrentBatteryBulkRecharge")
				decimals: 0
				unit: "A"
				min: 5
				max: 500
				step: 5
			}
		}
		MbSpinBox {
			id: idCurrentAcINMaxBulkRecharge
			description: qsTr("Max allowed current on AC-IN during bulk recharge")
			writeAccessLevel: User.AccessInstaller
			item {
				bind: Utils.path(settingsPrefix,"/CurrentAcINMaxBulkRecharge")
				decimals: 1
				unit: "A"
				min: 1
				max: 32
				step: 0.1
			}
		}
	}
}
				
	